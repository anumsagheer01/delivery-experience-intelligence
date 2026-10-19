"""Olist ingestion: download from the official Olist GitHub mirror, validate schema.

Source: https://github.com/olist/work-at-olist-data (Olist's official repo,
datasets/ directory). 9 CSV files, ~100k orders, 2016-2018.
"""
import os

import pandas as pd

from ..logging import get_logger

log = get_logger(__name__)

BASE_URL = "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets"

FILES = [
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_customers_dataset.csv",
    "olist_sellers_dataset.csv",
    "olist_products_dataset.csv",
    "olist_geolocation_dataset.csv",
    "product_category_name_translation.csv",
]

# expected columns per file (schema contract; validation fails loudly on drift)
SCHEMAS = {
    "olist_orders_dataset.csv": ["order_id", "customer_id", "order_status",
        "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date",
        "order_estimated_delivery_date"],
    "olist_customers_dataset.csv": ["customer_id", "customer_unique_id",
        "customer_zip_code_prefix", "customer_city", "customer_state"],
    "olist_order_reviews_dataset.csv": ["review_id", "order_id", "review_score",
        "review_comment_title", "review_comment_message",
        "review_creation_date", "review_answer_timestamp"],
}


def download(out_dir: str, files: list = None) -> list:
    """Download CSVs with requests (stdlib-friendly, no Kaggle credentials)."""
    import requests
    os.makedirs(out_dir, exist_ok=True)
    files = files or FILES
    paths = []
    for name in files:
        url = f"{BASE_URL}/{name}"
        dest = os.path.join(out_dir, name)
        if os.path.exists(dest):
            log.info("exists, skipping: %s", dest)
        else:
            log.info("downloading %s", url)
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            with open(dest, "wb") as f:
                f.write(r.content)
        paths.append(dest)
    return paths


def validate_schema(path: str) -> list:
    """Return list of schema violations (empty means OK)."""
    name = os.path.basename(path)
    df = pd.read_csv(path, nrows=5)
    expected = SCHEMAS.get(name)
    if not expected:
        return []
    missing = [c for c in expected if c not in df.columns]
    extra = [c for c in df.columns if c not in expected]
    problems = []
    if missing:
        problems.append(f"{name}: missing columns {missing}")
    if extra:
        log.warning("%s: unexpected columns %s (tolerated)", name, extra)
    return problems


TIMESTAMP_COLS = ["order_purchase_timestamp", "order_approved_at",
                  "order_delivered_carrier_date", "order_delivered_customer_date",
                  "order_estimated_delivery_date"]


def quality_report(orders_path: str) -> dict:
    """Data-quality facts about the orders table. All numbers measured here."""
    df = pd.read_csv(orders_path, parse_dates=TIMESTAMP_COLS)
    delivered = df[df.order_status == "delivered"].copy()
    delivered["is_late"] = (
        delivered.order_delivered_customer_date > delivered.order_estimated_delivery_date
    )
    report = {
        "n_orders": len(df),
        "n_delivered": len(delivered),
        "status_counts": df.order_status.value_counts().to_dict(),
        "late_rate_pct": round(100 * delivered.is_late.mean(), 2),
        "null_delivery_date_pct": round(
            100 * df.order_delivered_customer_date.isna().mean(), 2),
        "purchase_min": str(df.order_purchase_timestamp.min()),
        "purchase_max": str(df.order_purchase_timestamp.max()),
    }
    log.info("quality report: %s", report)
    return report
