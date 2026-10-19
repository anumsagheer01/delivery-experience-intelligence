"""Unit tests: streaming replay idempotency and schema."""
import json

from src.streaming import iter_events, to_iso


def test_to_iso_valid():
    assert to_iso("2018-01-15 10:23:45") == "2018-01-15T10:23:45Z"


def test_to_iso_blank():
    assert to_iso("") is None
    assert to_iso(None) is None


def test_event_ids_stable_and_unique(tmp_path):
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text(
        "order_id,customer_id,order_status,order_purchase_timestamp,"
        "order_approved_at,order_delivered_carrier_date,"
        "order_delivered_customer_date,order_estimated_delivery_date\n"
        "o1,c1,delivered,2018-01-01 10:00:00,2018-01-01 11:00:00,"
        "2018-01-05 09:00:00,2018-01-06 10:00:00,2018-01-08 00:00:00\n")
    events = list(iter_events(str(csv_path)))
    assert len(events) == 4
    ids = [e["event_id"] for e in events]
    assert len(set(ids)) == 4  # unique
    assert all(i.startswith("o1:") for i in ids)  # stable, order-scoped
    # every event is JSON-serializable with required fields
    for e in events:
        json.dumps(e)
        assert {"event_id", "order_id", "event_type", "event_time"} <= set(e)
