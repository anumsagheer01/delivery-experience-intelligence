"""Intervention agent: deterministic policy + Gemini reasoning, dry-run by default.

Loop per event: observe -> gather context (tools) -> reason -> act -> audit.
The policy layer (policy.md) decides eligible actions; Gemini assists with
explanation and drafting. Nothing external is ever sent automatically.
"""
import json
from datetime import datetime, timezone

from ..logging import get_logger

log = get_logger(__name__)

BAD_POD = {"no_package", "wrong_location", "unsafe_placement"}
ESCALATION_THRESHOLD = 0.6  # provisional; validate before production use


def apply_policy(event: dict, context: dict) -> dict:
    """Deterministic policy. Returns action, confidence, rationale.

    context keys: pod_quality (dict|None), risk_score (float|None),
                  order (dict|None)
    """
    pod = (context.get("pod_quality") or {}).get("quality")
    risk = context.get("risk_score")
    order = context.get("order") or {}
    reasons = []

    if pod in BAD_POD:
        reasons.append(f"POD quality flag: {pod}")
    if risk is not None and risk >= 0.7:
        reasons.append(f"late-delivery risk score {risk:.2f} >= 0.70")
    if order.get("is_late") and (order.get("review_score") or 5) <= 2:
        reasons.append("order late with low review score")

    confidence = 0.9 if len(reasons) >= 2 else (0.7 if reasons else 0.95)

    if not reasons:
        action = "no_action"
    elif confidence < ESCALATION_THRESHOLD:
        action = "escalate"
    elif pod in BAD_POD:
        action = "draft_driver_alert"
    else:
        action = "draft_customer_message"

    return {"action": action, "confidence": confidence,
            "rationale": "; ".join(reasons) or "no risk signals",
            "decided_at": datetime.now(timezone.utc).isoformat()}


def draft_messages(action: str, event: dict, context: dict,
                   llm_drafter=None) -> dict:
    """Produce message drafts. llm_drafter(event, context, kind) optional;
    falls back to transparent templates so dry-runs work without an LLM."""
    order_id = event.get("order_id", "unknown")
    if action == "draft_driver_alert":
        pod = (context.get("pod_quality") or {}).get("quality", "unknown")
        text = (f"[DRAFT - driver] Order {order_id}: the delivery photo was "
                f"flagged ({pod}). Please retake the photo at the customer's "
                f"door with the package clearly visible.")
    elif action == "draft_customer_message":
        text = (f"[DRAFT - customer] Order {order_id}: your delivery is "
                f"taking longer than expected. We are monitoring it and will "
                f"update you with a new estimate shortly.")
    else:
        text = ""
    if llm_drafter and text:
        text = llm_drafter(event, context, action)
    return {"draft": text}


def audit_record(event: dict, decision: dict, drafts: dict) -> dict:
    return {
        "event_id": event.get("event_id"),
        "order_id": event.get("order_id"),
        "event_type": event.get("event_type"),
        "action": decision["action"],
        "confidence": decision["confidence"],
        "rationale": decision["rationale"],
        "draft": drafts.get("draft", ""),
        "decided_at": decision["decided_at"],
    }


def handle_event(event: dict, context: dict, dry_run: bool = True,
                 llm_drafter=None, audit_sink=None) -> dict:
    """One agentic turn. Returns the audit record. Writes it unless dry_run."""
    decision = apply_policy(event, context)
    drafts = draft_messages(decision["action"], event, context, llm_drafter)
    record = audit_record(event, decision, drafts)
    if decision["action"] == "escalate":
        record["escalation"] = True
    if not dry_run and audit_sink:
        audit_sink(record)
    log.info("event %s -> %s (conf %.2f)",
             event.get("event_id"), decision["action"], decision["confidence"])
    return record
