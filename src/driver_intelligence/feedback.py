"""Driver feedback pipeline: validate, authorize, record, update memory.

Rules, all deterministic:
- Unverified driver feedback NEVER silently replaces a verified
  customer instruction. It flags and downgrades, it does not overwrite.
- gate_code_incorrect: a verified gate code becomes invalid pending
  verification. It is never shown as confirmed again until an explicit
  re-verification (see StopMemoryStore.reverify_gate_code).
- entrance_inaccessible, placement_outdated, locker_unavailable,
  instructions_changed, access_problem: append an unverified
  observation, record the problem on the profile, and flag the stored
  instruction for review. Verified customer text stays intact.
- Feedback containing a prompt injection pattern is recorded as an
  injection attempt and is not applied as an instruction.
- Every update returns BEFORE and AFTER state so the trace is checkable.
"""

from ..logging import get_logger
from .memory import (
    FEEDBACK_TYPES,
    Observation,
    looks_like_injection,
    now_iso,
    redact_text,
)

log = get_logger(__name__)


def _snapshot(store, stop_id):
    profile = store.get_profile(stop_id)
    return profile.to_dict() if profile else None


def process_feedback(store, feedback: dict, agent_trace_owner=None) -> dict:
    trace = []
    def add(tool, args, result, decision="", rule=""):
        trace.append({"step": len(trace) + 1, "tool": tool,
                      "arguments": {k: redact_text(v) if isinstance(v, str) else v
                                    for k, v in args.items()},
                      "result": redact_text(result),
                      "decision": decision, "rule": rule})
    feedback_type = feedback.get("feedback_type", "")
    driver_id = feedback.get("driver_id", "")
    stop_id = feedback.get("stop_id", "")
    note = feedback.get("note", "") or ""
    if feedback_type not in FEEDBACK_TYPES:
        add("validate_feedback", {"feedback_type": feedback_type},
            f"invalid feedback type: {feedback_type}",
            decision="reject feedback",
            rule="VALIDATION_RULE: feedback type must be one of the six known types")
        return {"applied": False, "reason": "invalid feedback type",
                "trace": trace, "decisions": [t for t in trace if t["decision"]]}
    if not driver_id or not stop_id:
        add("validate_feedback", {"feedback_type": feedback_type},
            "missing driver_id or stop_id",
            decision="reject feedback",
            rule="VALIDATION_RULE: driver and stop are required")
        return {"applied": False, "reason": "missing driver_id or stop_id",
                "trace": trace, "decisions": [t for t in trace if t["decision"]]}
    authorized = store.is_authorized(driver_id, stop_id)
    add("check_authorization", {"driver_id": driver_id, "stop_id": stop_id},
        "authorized" if authorized else "not authorized",
        decision="proceed" if authorized else "refuse feedback",
        rule="AUTHORIZATION_RULE: driver must be assigned to the stop")
    if not authorized:
        return {"applied": False, "reason": "unauthorized",
                "trace": trace, "decisions": [t for t in trace if t["decision"]]}
    before = _snapshot(store, stop_id)
    add("get_stop_memory", {"stop_id": stop_id},
        f"before verification={before['verification_status'] if before else 'none'}; "
        f"gate={before['gate_verification_status'] if before else 'none'}")
    if looks_like_injection(note):
        store.record_feedback_row(driver_id, stop_id, feedback_type, note,
                                  applied="rejected_injection")
        add("check_prompt_injection", {"stop_id": stop_id},
            "injection pattern detected in feedback note; not applied",
            decision="record as injection attempt only",
            rule="INJECTION_RULE: injected text never becomes an instruction")
        return {"applied": False, "reason": "injection attempt rejected",
                "before": before, "after": before,
                "trace": trace, "decisions": [t for t in trace if t["decision"]]}
    store.add_observation(Observation(
        stop_id=stop_id, kind=feedback_type, text=note,
        source_type="unverified_driver", verification_status="unverified",
        created_at=now_iso()))
    add("record_observation", {"stop_id": stop_id, "feedback_type": feedback_type},
        "append-only observation recorded as unverified_driver",
        decision="append history, do not overwrite verified instructions",
        rule="HISTORY_RULE: observations are append-only; verified customer "
             "instructions are never overwritten by driver claims")
    profile = store.get_profile(stop_id)
    applied_note = "observation recorded; verified instructions kept"
    if profile is not None:
        if feedback_type == "gate_code_incorrect":
            old = profile.gate_verification_status
            profile.gate_verification_status = "invalid"
            profile.known_access_problems = (
                (profile.known_access_problems + "; " if profile.known_access_problems else "")
                + "Driver reported gate code incorrect (synthetic feedback).")
            store.upsert_profile(profile)
            applied_note = (f"gate code status {old} -> invalid pending "
                            "verification; re-verification required")
            add("apply_update_rule", {"feedback_type": feedback_type},
                applied_note,
                decision="invalidate gate code, keep customer instruction text",
                rule="GATE_RULE: a reported-bad gate code loses verified "
                     "status and is never shown as confirmed again")
        elif feedback_type in ("entrance_inaccessible", "placement_outdated",
                               "locker_unavailable", "access_problem"):
            profile.known_access_problems = (
                (profile.known_access_problems + "; " if profile.known_access_problems else "")
                + f"Driver reported {feedback_type} (synthetic feedback).")
            if profile.confidence and profile.confidence > 0.5:
                profile.confidence = 0.5
            store.upsert_profile(profile)
            applied_note = "access problem recorded; instruction flagged for review"
            add("apply_update_rule", {"feedback_type": feedback_type},
                applied_note,
                decision="flag and downgrade confidence, do not overwrite",
                rule="FEEDBACK_RULE: unverified driver feedback flags and "
                     "downgrades, never silently replaces customer instructions")
        else:  # instructions_changed
            profile.known_access_problems = (
                (profile.known_access_problems + "; " if profile.known_access_problems else "")
                + "Driver reported instructions changed (synthetic feedback); "
                "flagged for customer re-verification.")
            store.upsert_profile(profile)
            applied_note = "instructions change flagged for re-verification"
            add("apply_update_rule", {"feedback_type": feedback_type},
                applied_note,
                decision="flag for customer re-verification, keep current text",
                rule="FEEDBACK_RULE: unverified driver feedback flags and "
                     "downgrades, never silently replaces customer instructions")
    store.record_feedback_row(driver_id, stop_id, feedback_type, note,
                              applied="applied")
    after = _snapshot(store, stop_id)
    add("record_audit", {"stop_id": stop_id},
        f"after verification={after['verification_status'] if after else 'none'}; "
        f"gate={after['gate_verification_status'] if after else 'none'}",
        decision="feedback applied as flag/downgrade",
        rule="AUDIT_RULE: every feedback decision is recorded with before "
             "and after state")
    result = {"applied": True, "reason": applied_note, "before": before,
              "after": after, "trace": trace,
              "decisions": [t for t in trace if t["decision"]]}
    if agent_trace_owner is not None:
        agent_trace_owner.trace_log.append(result)
    log.info("feedback %s for %s applied", feedback_type, stop_id)
    return result
