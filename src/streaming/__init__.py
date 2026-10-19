"""Event streaming replay: real Olist lifecycle timestamps as a Pub/Sub stream.

Replaying history through the live topic is the standard backfill pattern:
it validates schemas, throughput, and downstream queries with known-good data
before live traffic exists. This is NOT simulated data; every event carries a
real Olist timestamp.

Two execution modes:
  local  : writes newline-delimited JSON events to a file (runs anywhere)
  pubsub : publishes to Google Pub/Sub (needs GCP credentials)
"""
import csv
import json
import os
import time
import uuid
from datetime import datetime

from ..logging import get_logger

log = get_logger(__name__)

EVENTS = [
    ("ORDER_PURCHASED", "order_purchase_timestamp"),
    ("ORDER_APPROVED", "order_approved_at"),
    ("CARRIER_HANDOFF", "order_delivered_carrier_date"),
    ("DELIVERED", "order_delivered_customer_date"),
]


def to_iso(ts: str):
    ts = (ts or "").strip()
    if not ts:
        return None
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").isoformat() + "Z"
    except ValueError:
        return None


def iter_events(csv_path: str, max_orders: int = 0):
    """Yield event dicts with stable ids: f"{order_id}:{event_type}"."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            if max_orders and i >= max_orders:
                break
            for event_type, col in EVENTS:
                ts = to_iso(row.get(col))
                if not ts:
                    continue
                yield {
                    "event_id": f"{row['order_id']}:{event_type}",
                    "order_id": row["order_id"],
                    "event_type": event_type,
                    "event_time": ts,          # event time: when it really happened
                    "processed_time": datetime.utcnow().isoformat() + "Z",
                    "order_status": row.get("order_status", ""),
                }


def run_local(csv_path: str, out_path: str, max_orders: int = 20000,
              pace: int = 2000) -> dict:
    """Write events to JSONL, paced. Returns throughput stats."""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    n, start, last = 0, time.time(), time.time()
    with open(out_path, "w", encoding="utf-8") as f:
        for ev in iter_events(csv_path, max_orders):
            f.write(json.dumps(ev) + "\n")
            n += 1
            if n % pace == 0:
                elapsed = time.time() - last
                if elapsed < 1.0:
                    time.sleep(1.0 - elapsed)
                last = time.time()
    total = time.time() - start
    stats = {"events": n, "seconds": round(total, 1),
             "events_per_sec": round(n / max(total, 1e-6), 1), "out": out_path}
    log.info("replay stats: %s", stats)
    return stats


def run_pubsub(csv_path: str, project: str, topic: str,
               max_orders: int = 20000) -> dict:
    """Publish to real Pub/Sub. Needs google-cloud-pubsub + credentials."""
    from google.cloud import pubsub_v1
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project, topic)
    n, futures = 0, []
    for ev in iter_events(csv_path, max_orders):
        futures.append(publisher.publish(
            topic_path, json.dumps(ev).encode(),
            event_id=ev["event_id"]))  # attribute enables dedup downstream
        n += 1
    for fut in futures:
        fut.result()
    log.info("published %d events to %s", n, topic_path)
    return {"events": n, "topic": topic_path}
