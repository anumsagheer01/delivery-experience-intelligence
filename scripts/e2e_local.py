#!/usr/bin/env python3
"""Local end-to-end agent loop test on REAL Olist data (no GCP needed).

Pipeline: replay real order events (src.streaming.iter_events) ->
attach real order outcomes (is_late, min review_score from the CSVs) ->
run the intervention agent (dry_run) -> audit records ->
verify policy behavior on the real outcomes.

This validates the full loop logic. The cloud variant
(scripts/e2e_agent_cloud.py) swaps the CSV lookups for BigQuery and adds
BQML risk scores via src/agents/cloud_context.py; the policy is identical.

Usage: python scripts/e2e_local.py [--orders N]
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents import handle_event  # noqa: E402
from src.streaming import iter_events  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data", "raw", "olist")
# fall back to an alternate download location if present
ALT = os.path.join(os.path.expanduser("~"), "workspace", "build", "data", "raw")


def load_outcomes():
    orders_path = os.path.join(DATA, "olist_orders_dataset.csv")
    if not os.path.exists(orders_path):
        orders_path = os.path.join(ALT, "olist", "olist_orders_dataset.csv")
    base = os.path.dirname(orders_path)
    outcomes = {}
    with open(orders_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["order_status"] != "delivered":
                continue
            outcomes[row["order_id"]] = {
                "is_late": bool(row["order_delivered_customer_date"]
                                and row["order_estimated_delivery_date"]
                                and row["order_delivered_customer_date"]
                                > row["order_estimated_delivery_date"]),
                "review_score": None,
            }
    with open(os.path.join(base, "olist_order_reviews_dataset.csv"),
              newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            o = outcomes.get(row["order_id"])
            if o is None:
                continue
            s = int(row["review_score"])
            if o["review_score"] is None or s < o["review_score"]:
                o["review_score"] = s
    return outcomes, orders_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", type=int, default=2000)
    args = ap.parse_args()

    outcomes, orders_path = load_outcomes()
    print(f"orders with outcomes: {len(outcomes)}")

    records, by_action = [], {}
    late_low = 0
    late_low_actioned = 0
    for ev in iter_events(orders_path, max_orders=args.orders):
        if ev["event_type"] != "DELIVERED":
            continue
        o = outcomes.get(ev["order_id"])
        context = {"order": o, "risk_score": None, "pod_quality": None}
        rec = handle_event(ev, context, dry_run=True)
        records.append(rec)
        by_action[rec["action"]] = by_action.get(rec["action"], 0) + 1
        if o and o["is_late"] and (o["review_score"] or 5) <= 2:
            late_low += 1
            if rec["action"] == "draft_customer_message":
                late_low_actioned += 1

    print(f"DELIVERED events processed: {len(records)}")
    print(f"action mix: {by_action}")
    print(f"late+low-review orders: {late_low}, "
          f"got draft_customer_message: {late_low_actioned}")
    assert late_low_actioned == late_low, "policy missed a late+low-review order"
    assert by_action.get("no_action", 0) > 0, "expected some no_action"
    out = "evals/agent/e2e_local_results.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({"events": len(records), "action_mix": by_action,
                   "late_low": late_low,
                   "late_low_actioned": late_low_actioned}, f, indent=2)
    print(f"wrote {out}")
    print("E2E LOCAL: PASS")


if __name__ == "__main__":
    main()
