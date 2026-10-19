#!/usr/bin/env python3
"""Render dashboard preview charts from real data (matplotlib fallback).

Outputs PNGs to dashboard/preview/. Every chart is computed from the
downloaded datasets; no mock values.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src.logging import get_logger  # noqa: E402

log = get_logger(__name__)
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "dashboard", "preview")
os.makedirs(OUT, exist_ok=True)


def chart_late_by_state(olist_dir):
    o = pd.read_csv(f"{olist_dir}/olist_orders_dataset.csv",
                    parse_dates=["order_delivered_customer_date",
                                 "order_estimated_delivery_date"])
    c = pd.read_csv(f"{olist_dir}/olist_customers_dataset.csv")
    d = o[o.order_status == "delivered"].dropna(
        subset=["order_delivered_customer_date"]).merge(c, on="customer_id")
    d["is_late"] = (d.order_delivered_customer_date
                    > d.order_estimated_delivery_date)
    g = d.groupby("customer_state").agg(late_rate=("is_late", "mean"),
                                        n=("is_late", "size"))
    g = g[g.n >= 500].sort_values("late_rate", ascending=False).head(12)
    plt.figure(figsize=(10, 5))
    plt.bar(g.index, g.late_rate * 100)
    plt.title("Late-delivery rate by state (Olist, states with 500+ orders)")
    plt.ylabel("late %")
    plt.tight_layout()
    plt.savefig(f"{OUT}/late_by_state.png", dpi=120)
    plt.close()
    log.info("late_by_state.png")


def chart_review_by_late(olist_dir):
    o = pd.read_csv(f"{olist_dir}/olist_orders_dataset.csv",
                    parse_dates=["order_delivered_customer_date",
                                 "order_estimated_delivery_date"])
    r = pd.read_csv(f"{olist_dir}/olist_order_reviews_dataset.csv")
    d = o[o.order_status == "delivered"].dropna(
        subset=["order_delivered_customer_date"]).merge(r, on="order_id")
    d["is_late"] = (d.order_delivered_customer_date
                    > d.order_estimated_delivery_date)
    plt.figure(figsize=(8, 5))
    for late, grp in d.groupby("is_late"):
        plt.hist(grp.review_score, bins=range(1, 7), alpha=0.6,
                 label="late" if late else "on time", align="left")
    plt.title("Review score distribution: late vs on-time (Olist)")
    plt.xlabel("review score")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{OUT}/review_by_late.png", dpi=120)
    plt.close()
    log.info("review_by_late.png")


def chart_zone_fragmentation(amazon_dir):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.ingestion.amazon import (load_routes, load_sequences,
                                      zone_fragmentation)
    routes, stops = load_routes(f"{amazon_dir}/route_data.json")
    seqs = load_sequences(f"{amazon_dir}/actual_sequences.json")
    zf = zone_fragmentation(stops, seqs)
    plt.figure(figsize=(8, 5))
    plt.hist(zf.zone_revisits, bins=range(0, 15), align="left")
    plt.title("Zone revisits per route (Amazon Last-Mile, 6,112 routes)")
    plt.xlabel("zones re-entered after leaving")
    plt.tight_layout()
    plt.savefig(f"{OUT}/zone_revisits.png", dpi=120)
    plt.close()
    log.info("zone_revisits.png")


def main():
    ap = argparse.ArgumentParser(
        description="Render dashboard preview charts from real data.")
    ap.add_argument("--olist-dir", default="data/raw/olist",
                    help="Olist dataset directory")
    ap.add_argument("--amazon-dir", default="data/raw/amazon",
                    help="Amazon routing dataset directory")
    ap.add_argument("--out-dir", default=None,
                    help="Output directory (default: dashboard/preview/)")
    args = ap.parse_args()
    global OUT
    if args.out_dir:
        OUT = args.out_dir
        os.makedirs(OUT, exist_ok=True)
    chart_late_by_state(args.olist_dir)
    chart_review_by_late(args.olist_dir)
    chart_zone_fragmentation(args.amazon_dir)
    print("charts in", OUT)


if __name__ == "__main__":
    main()
