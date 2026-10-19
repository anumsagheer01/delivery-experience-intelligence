#!/usr/bin/env python3
"""Publish real Olist order-lifecycle events to Pub/Sub (Cloud Shell).

Every event carries a real Olist timestamp from olist_orders_dataset.csv.
Mirrors src/streaming/__init__.py iter_events/run_pubsub exactly.
"""
import csv
import json
import time
from datetime import datetime

from google.cloud import pubsub_v1

PROJECT = "delivery-experience-511901"
TOPIC = "dei-order-events"
CSV_PATH = "/home/anumsagheer3/dei-data/olist/olist_orders_dataset.csv"
MAX_ORDERS = 5000

EVENTS = [
    ("ORDER_PURCHASED", "order_purchase_timestamp"),
    ("ORDER_APPROVED", "order_approved_at"),
    ("CARRIER_HANDOFF", "order_delivered_carrier_date"),
    ("DELIVERED", "order_delivered_customer_date"),
]


def to_iso(ts):
    ts = (ts or "").strip()
    if not ts:
        return None
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").isoformat() + "Z"
    except ValueError:
        return None


def main():
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT, TOPIC)
    n, start, futures = 0, time.time(), []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            if i >= MAX_ORDERS:
                break
            for event_type, col in EVENTS:
                ts = to_iso(row.get(col))
                if not ts:
                    continue
                ev = {
                    "event_id": row["order_id"] + ":" + event_type,
                    "order_id": row["order_id"],
                    "event_type": event_type,
                    "event_time": ts,
                    "processed_time": datetime.utcnow().isoformat() + "Z",
                    "order_status": row.get("order_status", ""),
                }
                futures.append(publisher.publish(topic_path, json.dumps(ev).encode()))
                n += 1
    for fut in futures:
        fut.result()
    elapsed = time.time() - start
    print("published: %d seconds: %.1f events_per_sec: %.1f"
          % (n, elapsed, n / max(elapsed, 1e-6)))


if __name__ == "__main__":
    main()
