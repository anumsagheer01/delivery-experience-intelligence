#!/usr/bin/env python3
"""Agent dry-run evaluation: policy decisions on controlled scenarios.

Each scenario pairs a synthetic event with context assembled from REAL
artifacts (risk model thresholds, Olist order rows). Scenarios are labeled
with the expected action; the harness reports agreement. Nothing is sent;
dry_run=True throughout.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents import handle_event  # noqa: E402
from src.logging import get_logger  # noqa: E402

log = get_logger(__name__)

SCENARIOS = [
    {"name": "normal_delivery",
     "event": {"event_id": "t1:DELIVERED", "order_id": "t1", "event_type": "DELIVERED"},
     "context": {"risk_score": 0.12,
                 "pod_quality": {"quality": "good", "confidence": 0.95}},
     "expected": "no_action"},
    {"name": "bad_pod_photo",
     "event": {"event_id": "t2:DELIVERED", "order_id": "t2", "event_type": "DELIVERED"},
     "context": {"risk_score": 0.2,
                 "pod_quality": {"quality": "no_package", "confidence": 0.88}},
     "expected": "draft_driver_alert"},
    {"name": "high_late_risk",
     "event": {"event_id": "t3:ORDER_PURCHASED", "order_id": "t3",
               "event_type": "ORDER_PURCHASED"},
     "context": {"risk_score": 0.85, "pod_quality": None},
     "expected": "draft_customer_message"},
    {"name": "late_and_bad_review",
     "event": {"event_id": "t4:DELIVERED", "order_id": "t4", "event_type": "DELIVERED"},
     "context": {"risk_score": 0.5,
                 "order": {"is_late": True, "review_score": 1},
                 "pod_quality": {"quality": "good", "confidence": 0.9}},
     "expected": "draft_customer_message"},
    {"name": "missing_data",
     "event": {"event_id": "t5:DELIVERED", "order_id": "t5", "event_type": "DELIVERED"},
     "context": {},
     "expected": "no_action"},
]


def main(out_path="evals/agent/dry_run_results.json"):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    results = []
    for s in SCENARIOS:
        rec = handle_event(s["event"], s["context"], dry_run=True)
        ok = rec["action"] == s["expected"]
        results.append({"scenario": s["name"], "expected": s["expected"],
                        "got": rec["action"], "match": ok,
                        "confidence": rec["confidence"],
                        "rationale": rec["rationale"]})
        log.info("%s: expected=%s got=%s %s",
                 s["name"], s["expected"], rec["action"],
                 "OK" if ok else "MISMATCH")
    agree = sum(r["match"] for r in results)
    summary = {"scenarios": len(results), "agreement": agree,
               "results": results}
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"agent dry-run: {agree}/{len(results)} scenarios match expected action")
    print(f"results -> {out_path}")


if __name__ == "__main__":
    main()
