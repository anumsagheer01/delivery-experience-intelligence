#!/usr/bin/env python3
"""Cloud end-to-end agent loop (runs in Cloud Shell, needs GCP credentials).

Pipeline: take real order_ids -> build context from BigQuery
(src/agents/cloud_context.py: order facts + BQML ML.PREDICT risk score) ->
run the intervention agent (dry_run) -> audit records ->
write audit table dei_mart.agent_audit.

Usage (Cloud Shell): python3 scripts/e2e_agent_cloud.py [--orders N]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.cloud import bigquery  # noqa: E402

from src.agents import handle_event  # noqa: E402
from src.agents.cloud_context import LOCATION, PROJECT, build_context  # noqa: E402

AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS `delivery-experience-511901.dei_mart.agent_audit` (
  event_id STRING, order_id STRING, event_type STRING, action STRING,
  confidence FLOAT64, rationale STRING, draft STRING, decided_at TIMESTAMP
) OPTIONS(description='Intervention agent audit trail (dry-run).')
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", type=int, default=500)
    args = ap.parse_args()

    client = bigquery.Client(project=PROJECT, location=LOCATION)
    client.query(AUDIT_DDL).result()

    rows = list(client.query(
        "SELECT order_id FROM `delivery-experience-511901.dei_mart.orders` "
        "WHERE order_status = 'delivered' "
        "ORDER BY order_purchase_timestamp DESC LIMIT %d" % args.orders
    ).result())
    print(f"scoring {len(rows)} real orders through the agent")

    records, by_action = [], {}
    for r in rows:
        oid = r["order_id"]
        event = {"event_id": oid + ":DELIVERED", "order_id": oid,
                 "event_type": "DELIVERED"}
        context = build_context(oid, client)
        rec = handle_event(event, context, dry_run=True)
        records.append(rec)
        by_action[rec["action"]] = by_action.get(rec["action"], 0) + 1

    print(f"action mix: {by_action}")
    table_rows = [{
        "event_id": r["event_id"], "order_id": r["order_id"],
        "event_type": r["event_type"], "action": r["action"],
        "confidence": r["confidence"], "rationale": r["rationale"],
        "draft": r["draft"], "decided_at": r["decided_at"],
    } for r in records]
    errors = client.insert_rows_json(
        "delivery-experience-511901.dei_mart.agent_audit", table_rows)
    assert not errors, errors
    print(f"wrote {len(table_rows)} audit rows to dei_mart.agent_audit")

    out = "/home/anumsagheer3/dei-data/e2e_cloud_results.json"
    with open(out, "w") as f:
        json.dump({"orders": len(rows), "action_mix": by_action}, f, indent=2)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
