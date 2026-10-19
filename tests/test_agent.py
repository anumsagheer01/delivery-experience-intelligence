"""Unit tests: agent policy decisions and guardrails."""
from src.agents import apply_policy, handle_event


def test_no_signals_no_action():
    d = apply_policy({"event_id": "o1:ORDER_PURCHASED"}, {})
    assert d["action"] == "no_action"


def test_bad_pod_alerts_driver():
    d = apply_policy({"event_id": "o1:DELIVERED"},
                     {"pod_quality": {"quality": "no_package"}})
    assert d["action"] == "draft_driver_alert"


def test_high_risk_customer_message():
    d = apply_policy({"event_id": "o1:ORDER_PURCHASED"}, {"risk_score": 0.85})
    assert d["action"] == "draft_customer_message"


def test_dry_run_writes_nothing():
    written = []
    rec = handle_event({"event_id": "o1:DELIVERED", "order_id": "o1",
                        "event_type": "DELIVERED"},
                       {"pod_quality": {"quality": "unsafe_placement"}},
                       dry_run=True, audit_sink=written.append)
    assert rec["action"] == "draft_driver_alert"
    assert written == []  # dry run: no side effects


def test_audit_record_has_rationale():
    rec = handle_event({"event_id": "o1:DELIVERED", "order_id": "o1",
                        "event_type": "DELIVERED"},
                       {"pod_quality": {"quality": "wrong_location"}})
    assert rec["rationale"] and rec["confidence"] > 0
