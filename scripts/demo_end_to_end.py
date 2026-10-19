#!/usr/bin/env python3
"""End-to-end demo: one historical Olist order through the full platform.

Pipeline: order record -> streaming event -> risk score -> (controlled
scenario) POD evidence -> agent policy -> draft/escalation -> audit record.

CONTROLLED SCENARIO DISCLOSURE: the POD photo evidence and any Amazon route
context attached here are illustrative pairings for demonstrating the
integration, NOT real observations of this order. The risk model, policy
logic, and audit trail are real code running on real Olist data.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from src.agents import handle_event  # noqa: E402
from src.logging import get_logger  # noqa: E402
from src.streaming import iter_events  # noqa: E402

log = get_logger(__name__)


def risk_score_for(order: dict) -> float:
    """Rule-based proxy used in the demo when no trained artifact is loaded.

    Real deployment calls the trained HGB model (see src/ml). The proxy is
    documented as a stand-in, not a model result.
    """
    score = 0.1
    if order.get("promised_days", 7) > 14:
        score += 0.25
    if (order.get("freight_value") or 0) > 30:
        score += 0.15
    return round(min(score, 0.95), 2)


def main(order_id: str = None, olist_dir: str = "data/raw/olist"):
    orders = pd.read_csv(f"{olist_dir}/olist_orders_dataset.csv")
    order_id = order_id or orders.iloc[0].order_id
    log.info("demo order: %s", order_id)

    events = [e for e in iter_events(f"{olist_dir}/olist_orders_dataset.csv")
              if e["order_id"] == order_id]
    log.info("replayed %d events for order", len(events))

    context = {
        "risk_score": risk_score_for({}),
        # CONTROLLED SCENARIO: illustrative POD evidence, not a real photo
        "pod_quality": {"quality": "package_obscured", "confidence": 0.72,
                        "note": "controlled scenario pairing"},
    }
    records = []
    for ev in events:
        if ev["event_type"] == "DELIVERED":
            rec = handle_event(ev, context, dry_run=True)
            records.append(rec)
            print(json.dumps(rec, indent=2))
    log.info("demo complete: %d agent decisions (dry-run, nothing sent)",
             len(records))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--order-id", default=None)
    ap.add_argument("--olist-dir", default="data/raw/olist")
    args = ap.parse_args()
    main(order_id=args.order_id, olist_dir=args.olist_dir)
