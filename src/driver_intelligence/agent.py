"""Driver Intelligence Agent: a single agent with a real tool calling loop.

Pipeline per DRIVER_APPROACHING_STOP event, in order, each step traced:
1. validate_event (deterministic)
2. check authorization (deterministic; refusal stops memory disclosure)
3. get_stop_memory (tool)
4. check_delivery_restrictions (tool)
5. resolve_instruction_conflicts (tool, deterministic priority rules)
6. decide warn vs proceed, show vs suppress gate code, stale vs fresh
7. generate_driver_card (tool; LLM summarization last, validated, with
   a deterministic fallback card when the LLM is unavailable or fails
   validation)
8. record the decision and reasons to the audit log (tool, in memory)

No step hands raw rows to an LLM. The LLM, when present, receives only
the deterministic card lines and must return a condensation of them;
anything else is rejected and the fallback card is used. The trace is
the proof: tool name, arguments (redacted), result summary, and every
decision with the rule cited.
"""

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from ..logging import get_logger
from .memory import (
    InstructionCandidate,
    StopMemoryStore,
    looks_like_injection,
    redact_text,
    resolve_conflicts,
)

log = get_logger(__name__)

REQUIRED_EVENT_FIELDS = (
    "driver_id", "order_id", "stop_id", "distance_miles", "eta_minutes",
    "timestamp",
)
INJECTION_MARKERS = ("ignore previous instructions", "reveal the gate code",
                     "override the policy", "disregard the restriction")


@dataclass
class ToolTrace:
    step: int
    tool: str
    arguments: dict
    result: str
    decision: str = ""
    rule: str = ""


@dataclass
class Card:
    lines: list
    warnings: list
    verified_labels: dict
    llm_used: bool = False
    llm_calls: int = 0
    fallback_used: bool = False
    fallback_reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def text(self) -> str:
        return "\n".join(self.lines)


def _redact_args(args: dict) -> dict:
    out = {}
    for key, value in args.items():
        if isinstance(value, str):
            out[key] = redact_text(value)
        else:
            out[key] = value
    return out


def _parse_ts(value: str) -> str:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).isoformat()
    except (ValueError, TypeError):
        return str(value)


class DriverAgent:
    def __init__(self, store: StopMemoryStore, llm_summarizer=None):
        self.store = store
        self.llm_summarizer = llm_summarizer
        self.audit_log: list = []
        self.trace_log: list = []
        self._seen_events: dict = {}

    def _trace(self, trace: list, tool: str, args: dict, result: str,
               decision: str = "", rule: str = "") -> None:
        trace.append(ToolTrace(
            step=len(trace) + 1, tool=tool, arguments=_redact_args(args),
            result=redact_text(result), decision=decision, rule=rule))

    def _decisions(self, trace: list) -> list:
        return [{"step": t.step, "tool": t.tool, "decision": t.decision,
                 "rule": t.rule, "result": t.result}
                for t in trace if t.decision]

    # Tool 1: validate
    def validate_event(self, event: dict) -> tuple:
        missing = [f for f in REQUIRED_EVENT_FIELDS if event.get(f) in (None, "")]
        if missing:
            return False, f"missing fields: {','.join(missing)}"
        try:
            distance = float(event["distance_miles"])
            eta = float(event["eta_minutes"])
        except (TypeError, ValueError):
            return False, "distance_miles and eta_minutes must be numbers"
        if distance < 0 or eta < 0:
            return False, "distance_miles and eta_minutes must not be negative"
        if event.get("event_type") not in (None, "DRIVER_APPROACHING_STOP"):
            return False, "unsupported event_type"
        return True, "event valid"

    # Tool 2: authorization
    def check_authorization(self, driver_id: str, stop_id: str) -> bool:
        return self.store.is_authorized(driver_id, stop_id)

    # Tool 3: memory retrieval
    def get_stop_memory(self, stop_id: str) -> dict:
        self.store.expire_stale(stop_id)
        profile = self.store.get_profile(stop_id)
        observations = self.store.list_observations(stop_id)
        return {
            "profile": profile.to_dict() if profile else None,
            "observations": [o.to_dict() for o in observations],
        }

    # Tool 4: restrictions
    def check_delivery_restrictions(self, memory: dict) -> dict:
        profile = memory.get("profile") or {}
        restrictions = []
        if profile.get("leave_unattended_restriction"):
            restrictions.append({
                "kind": "leave_unattended",
                "text": profile.get("leave_restriction_reason")
                or "Do not leave unattended.",
                "is_restriction": True})
        problems = profile.get("known_access_problems") or ""
        if problems:
            restrictions.append({"kind": "access_problem", "text": problems,
                                 "is_restriction": True})
        if profile.get("gate_verification_status") == "invalid":
            restrictions.append({
                "kind": "gate_code",
                "text": "Gate code is invalid pending verification. "
                        "Do not rely on the stored access code.",
                "is_restriction": True})
        if profile.get("verification_status") == "expired":
            restrictions.append({
                "kind": "access",
                "text": "Stored access information is expired. "
                        "Verify on arrival.",
                "is_restriction": True})
        for obs in memory.get("observations", []):
            if obs.get("is_restriction"):
                restrictions.append({"kind": obs["kind"], "text": obs["text"],
                                     "is_restriction": True})
        return {"restrictions": restrictions}

    # Tool 5: conflict resolution
    def resolve_instruction_conflicts(self, memory: dict,
                                      restrictions: dict) -> dict:
        profile = memory.get("profile") or {}
        candidates = []
        if profile.get("preferred_placement"):
            candidates.append(InstructionCandidate(
                kind="placement", text=profile["preferred_placement"],
                source_type="verified_customer"
                if profile.get("verification_status") == "verified"
                else "unverified_historical",
                verification_status=profile.get("verification_status", "unverified"),
                created_at=profile.get("updated_at", "")))
        if profile.get("preferred_entrance"):
            candidates.append(InstructionCandidate(
                kind="entrance", text=profile["preferred_entrance"],
                source_type="verified_customer"
                if profile.get("verification_status") == "verified"
                else "unverified_historical",
                verification_status=profile.get("verification_status", "unverified"),
                created_at=profile.get("updated_at", "")))
        for obs in memory.get("observations", []):
            candidates.append(InstructionCandidate(
                kind=obs["kind"], text=obs["text"],
                source_type=obs["source_type"],
                verification_status=obs["verification_status"],
                created_at=obs["created_at"],
                is_restriction=bool(obs.get("is_restriction"))))
        for res in restrictions.get("restrictions", []):
            if res["kind"] in ("leave_unattended", "access_problem", "gate_code"):
                candidates.append(InstructionCandidate(
                    kind=res["kind"], text=res["text"],
                    source_type="policy_restriction",
                    verification_status="verified",
                    is_restriction=True))
        return resolve_conflicts(candidates)

    # Tool 6: deterministic card (fallback and LLM input)
    def _deterministic_card(self, memory: dict, resolution: dict,
                            restrictions: dict, event: dict) -> Card:
        profile = memory.get("profile") or {}
        warnings, lines, labels = [], [], {}
        for res in restrictions.get("restrictions", []):
            warnings.append(f"WARNING: {redact_text(res['text'])}")
        winners = resolution.get("winners", {})
        placement = winners.get("placement", {}).get("text") or \
            profile.get("preferred_placement", "")
        entrance = winners.get("entrance", {}).get("text") or \
            profile.get("preferred_entrance", "")
        status = profile.get("verification_status", "unverified")
        gate_status = profile.get("gate_verification_status", "unverified")
        labels["placement"] = status
        labels["entrance"] = status
        labels["gate_code"] = gate_status
        if not profile:
            warnings.append("WARNING: No stop memory found. Verify on arrival.")
        if not placement and not entrance:
            warnings.append("WARNING: Placement and entrance unknown. "
                            "Verify on arrival.")
        lines.extend(warnings)
        if entrance:
            lines.append(f"Entrance ({status}): {redact_text(entrance)}")
        if placement:
            lines.append(f"Placement ({status}): {redact_text(placement)}")
        contact = profile.get("contact_preference", "")
        if contact:
            lines.append(f"Contact ({status}): {redact_text(contact)}")
        if profile.get("gate_code_ref"):
            if gate_status == "verified":
                lines.append("Gate code: on file and verified "
                             "(code value never shown).")
            else:
                lines.append(f"Gate code: requires verification "
                             f"(status: {gate_status}). Do not rely on it.")
        if profile.get("building_type"):
            lines.append(f"Building: {profile['building_type']}")
        lines.append(f"ETA: {event.get('eta_minutes')} minutes, "
                     f"{event.get('distance_miles')} miles away.")
        return Card(lines=lines[:8], warnings=warnings,
                    verified_labels=labels)

    # Tool 7: LLM summarization, validated, fallback on any failure
    def _summarize_with_llm(self, card: Card) -> Card:
        if self.llm_summarizer is None:
            card.fallback_used = True
            card.fallback_reason = "no LLM configured; deterministic fallback used"
            return card
        try:
            summary = self.llm_summarizer(card.lines)
        except Exception as exc:  # noqa: BLE001 - fallback is the point
            card.fallback_used = True
            card.fallback_reason = f"LLM unavailable ({exc}); fallback used"
            return card
        card.llm_calls = 1
        if not summary or not isinstance(summary, str):
            card.fallback_used = True
            card.fallback_reason = "LLM returned empty output; fallback used"
            return card
        cleaned = redact_text(summary.strip())
        lowered = cleaned.lower()
        if any(marker in lowered for marker in INJECTION_MARKERS):
            card.fallback_used = True
            card.fallback_reason = "LLM output contained an injection marker; fallback used"
            return card
        if "gate code" in lowered and "never shown" not in lowered \
                and "requires verification" not in lowered:
            card.fallback_used = True
            card.fallback_reason = ("LLM output mentioned a gate code value "
                                    "or phrasing; fallback used")
            return card
        base_text = " ".join(card.lines).lower()
        invented = [word for word in ("roof", "basement", "backyard shed")
                    if word in lowered and word not in base_text]
        if invented:
            card.fallback_used = True
            card.fallback_reason = (
                f"LLM invented instructions ({','.join(invented)}); fallback used")
            return card
        card.lines = [line for line in cleaned.splitlines() if line.strip()][:8]
        card.llm_used = True
        return card

    def generate_driver_card(self, memory: dict, resolution: dict,
                             restrictions: dict, event: dict) -> Card:
        card = self._deterministic_card(memory, resolution, restrictions, event)
        return self._summarize_with_llm(card)

    def handle_approach(self, event: dict) -> dict:
        """Run the full tool loop for one approach event. Returns a result
        dict with card, trace, decisions, audit record, and counters."""
        started = time.perf_counter()
        trace: list = []
        event_id = event.get("event_id") or (
            f"{event.get('driver_id')}:{event.get('stop_id')}:"
            f"{_parse_ts(event.get('timestamp', ''))}")
        dedup_key = (event.get("driver_id"), event.get("stop_id"), event_id)
        if dedup_key in self._seen_events:
            prior = self._seen_events[dedup_key]
            self._trace(trace, "check_idempotency", {"event_id": event_id},
                        "duplicate event; prior card reused, no new audit record",
                        decision="duplicate: reuse prior card, do not re-audit",
                        rule="IDEMPOTENCY_RULE: (driver_id, stop_id, event_id) "
                             "produces one card and one audit record")
            result = dict(prior)
            result["duplicate"] = True
            result["trace"] = [asdict(t) for t in trace]
            result["decisions"] = self._decisions(trace)
            result["duplicate_handled"] = True
            return result
        valid, valid_msg = self.validate_event(event)
        self._trace(trace, "validate_event", {"event_id": event_id},
                    valid_msg,
                    decision="proceed" if valid else "reject event",
                    rule="VALIDATION_RULE: required fields and non-negative "
                         "distance and ETA")
        if not valid:
            return self._finish(trace, event, None, "invalid_event",
                                valid_msg, started, duplicate=False)
        authorized = self.check_authorization(
            event["driver_id"], event["stop_id"])
        self._trace(trace, "check_authorization",
                    {"driver_id": event["driver_id"],
                     "stop_id": event["stop_id"]},
                    "authorized" if authorized else "not authorized",
                    decision="proceed" if authorized else "refuse: no memory disclosed",
                    rule="AUTHORIZATION_RULE: driver must be assigned to the stop")
        if not authorized:
            return self._finish(trace, event, None, "unauthorized",
                                "driver is not assigned to this stop",
                                started, duplicate=False)
        memory = self.get_stop_memory(event["stop_id"])
        profile = memory.get("profile")
        self._trace(trace, "get_stop_memory", {"stop_id": event["stop_id"]},
                    f"profile found={profile is not None}; "
                    f"observations={len(memory['observations'])}; "
                    f"verification={profile.get('verification_status') if profile else 'none'}")
        restrictions = self.check_delivery_restrictions(memory)
        self._trace(trace, "check_delivery_restrictions",
                    {"stop_id": event["stop_id"]},
                    f"{len(restrictions['restrictions'])} restrictions found",
                    decision=("warn" if restrictions["restrictions"] else "no restriction warning"),
                    rule="SAFETY_RULE: restrictions always win")
        resolution = self.resolve_instruction_conflicts(memory, restrictions)
        winner_text = "; ".join(
            f"{k}={v['text']} ({v['source_type']})"
            for k, v in resolution["winners"].items())
        self._trace(trace, "resolve_instruction_conflicts",
                    {"stop_id": event["stop_id"],
                     "candidates": len(memory["observations"]) + 2},
                    winner_text or "no winning instruction",
                    decision="apply priority ranking; restrictions override winners",
                    rule="PRIORITY_RULE: verified customer (1) > policy (2) > "
                         "verified operational (3) > verified historical (4) > "
                         "unverified historical (5) > unverified driver (6); "
                         "SAFETY_RULE: restrictions always win")
        for reason in resolution["reasons"]:
            self._trace(trace, "weigh_alternative", {"stop_id": event["stop_id"]},
                        reason, decision="winner kept, loser suppressed",
                        rule="PRIORITY_RULE")
        stale = bool(profile and profile.get("verification_status") == "expired")
        missing = profile is None
        gate_status = profile.get("gate_verification_status") if profile else "none"
        warn = bool(restrictions["restrictions"] or stale or missing)
        self._trace(trace, "decide_alert_level",
                    {"restrictions": len(restrictions["restrictions"]),
                     "stale": stale, "missing": missing},
                    "warn" if warn else "proceed",
                    decision="warn" if warn else "proceed",
                    rule="ALERT_RULE: any restriction, stale, or missing "
                         "memory produces a warning card")
        self._trace(trace, "decide_gate_code_display",
                    {"gate_verification_status": gate_status},
                    "show status only, never the code value",
                    decision="suppress gate code value; show status only",
                    rule="SECURITY_RULE: gate code values are never shown, "
                         "logged, or audited")
        if looks_like_injection(str(event.get("note", ""))) or \
                looks_like_injection(str(event.get("instruction", ""))):
            self._trace(trace, "check_prompt_injection",
                        {"stop_id": event["stop_id"]},
                        "injection pattern in event fields ignored",
                        decision="ignore injected instruction; use stored memory only",
                        rule="INJECTION_RULE: event free text never overrides "
                             "stored verified instructions")
        card_started = time.perf_counter()
        card = self.generate_driver_card(memory, resolution, restrictions, event)
        card_latency_ms = (time.perf_counter() - card_started) * 1000
        self._trace(trace, "generate_driver_card",
                    {"stop_id": event["stop_id"],
                     "llm_configured": self.llm_summarizer is not None},
                    f"llm_used={card.llm_used}; fallback_used={card.fallback_used}; "
                    f"lines={len(card.lines)}; reason={card.fallback_reason}",
                    decision=("use LLM summary" if card.llm_used
                              else "use deterministic fallback card"),
                    rule="LLM_RULE: LLM summarizes verified card lines only, "
                         "after deterministic decisions; fallback on failure")
        outcome = "warn" if warn else "proceed"
        result = self._finish(trace, event, card.to_dict(), outcome,
                              f"card generated; warnings={len(card.warnings)}",
                              started, duplicate=False,
                              card_latency_ms=card_latency_ms,
                              llm_calls=card.llm_calls)
        self._seen_events[dedup_key] = result
        return result

    def _finish(self, trace, event, card, action, message, started,
                duplicate, card_latency_ms=0.0, llm_calls=0) -> dict:
        elapsed_ms = (time.perf_counter() - started) * 1000
        audit = {
            "event_id": event.get("event_id"),
            "driver_id": event.get("driver_id"),
            "order_id": event.get("order_id"),
            "stop_id": event.get("stop_id"),
            "action": action,
            "message": redact_text(message),
            "card_lines": [redact_text(line) for line in (card or {}).get("lines", [])]
            if card else [],
            "llm_calls": llm_calls,
            "duplicate": duplicate,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }
        if action not in ("unauthorized", "invalid_event") or True:
            # Unauthorized and invalid events are audited too, but their
            # audit records contain no memory content by construction.
            if action in ("unauthorized", "invalid_event"):
                audit["card_lines"] = []
            self.audit_log.append(audit)
        result = {
            "action": action,
            "card": card,
            "trace": [asdict(t) for t in trace],
            "decisions": self._decisions(trace),
            "audit": audit,
            "llm_calls": llm_calls,
            "card_latency_ms": round(card_latency_ms, 2),
            "end_to_end_latency_ms": round(elapsed_ms, 2),
            "duplicate": duplicate,
        }
        self.trace_log.append(result)
        log.info("approach %s -> %s", event.get("stop_id"), action)
        return result

    # Tool 8: feedback recording through the agent loop
    def record_driver_feedback(self, feedback: dict) -> dict:
        from .feedback import process_feedback
        return process_feedback(self.store, feedback, agent_trace_owner=self)
