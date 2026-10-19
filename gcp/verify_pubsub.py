#!/usr/bin/env python3
"""Verify Pub/Sub delivery: pull all messages, count, check schema, ack."""
import json
import time

from google.cloud import pubsub_v1

PROJECT = "delivery-experience-511901"
SUB = "dei-order-events-sub"

subscriber = pubsub_v1.SubscriberClient()
sub_path = subscriber.subscription_path(PROJECT, SUB)

pulled, first, deadline = 0, None, time.time() + 150
while time.time() < deadline:
    resp = subscriber.pull(request={"subscription": sub_path, "max_messages": 1000},
                            timeout=20)
    if not resp.received_messages:
        break
    ack_ids = []
    for rm in resp.received_messages:
        pulled += 1
        ack_ids.append(rm.ack_id)
        if first is None:
            first = json.loads(rm.message.data.decode())
    subscriber.acknowledge(request={"subscription": sub_path, "ack_ids": ack_ids})
    if pulled >= 20000:
        break

print("pulled_total:", pulled)
if first:
    print("sample_keys:", sorted(first.keys()))
    print("sample:", json.dumps(first)[:300])
    assert set(first) == {"event_id", "order_id", "event_type",
                          "event_time", "processed_time", "order_status"}, "schema mismatch"
    print("schema OK")
