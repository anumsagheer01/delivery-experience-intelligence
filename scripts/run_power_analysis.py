"""Power analysis for the outreach experiment, from real Olist data.

Eligible population: customers with at least one late delivered order.
Outcome per customer: review score of their first late order (pre-registered).

Writes evals/experiments/power_analysis.json. All statistics are measured;
no treatment effect is assumed or claimed.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from src.experiments.design import ALPHA, MDE_STARS, N_LOOKS, TARGET_POWER
from src.experiments.power import (design_effect, obf_boundaries,
                                   sample_size_two_sample)
from src.experiments.analysis import cuped_gate

RAW = os.path.expanduser("~/workspace/build/data/raw/olist")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "evals", "experiments", "power_analysis.json")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

orders = pd.read_csv(os.path.join(RAW, "olist_orders_dataset.csv"))
customers = pd.read_csv(os.path.join(RAW, "olist_customers_dataset.csv"))
reviews = pd.read_csv(os.path.join(RAW, "olist_order_reviews_dataset.csv"))
items = pd.read_csv(os.path.join(RAW, "olist_order_items_dataset.csv"))

for c in ["order_delivered_customer_date", "order_estimated_delivery_date",
          "order_purchase_timestamp"]:
    orders[c] = pd.to_datetime(orders[c], errors="coerce")
delivered = orders[orders["order_status"] == "delivered"].copy()
delivered["is_late"] = (
    delivered["order_delivered_customer_date"]
    > delivered["order_estimated_delivery_date"]
)
delivered = delivered.merge(
    customers[["customer_id", "customer_unique_id"]], on="customer_id",
    how="left")

reviews["review_creation_date"] = pd.to_datetime(
    reviews["review_creation_date"], errors="coerce")
reviews = reviews.sort_values("review_creation_date").drop_duplicates(
    "order_id", keep="first")

late = delivered[delivered["is_late"]].merge(
    reviews[["order_id", "review_score"]], on="order_id", how="inner")
late = late.sort_values("order_purchase_timestamp")
# one row per customer: first late order's review (pre-registered rule)
eligible = late.drop_duplicates("customer_unique_id", keep="first")
y = eligible["review_score"].to_numpy(dtype=float)
baseline_mean = float(y.mean())
baseline_std = float(y.std())
n_eligible_hist = int(len(eligible))

# cluster size among eligible customers (late orders per customer)
late_per_cust = late.groupby("customer_unique_id").size()
mean_cluster = float(late_per_cust.mean())
# ICC proxy measured on all delivered orders with reviews (exploration file)
with open(os.path.join(ROOT, "evals", "experiments",
                       "data_exploration.json")) as f:
    explor = json.load(f)
icc = explor["within_customer_score_corr"]
deff = design_effect(mean_cluster, icc)

per_arm = sample_size_two_sample(baseline_std, MDE_STARS, ALPHA,
                                 TARGET_POWER)
per_arm_adj = per_arm * deff

# MDE table
mde_table = {}
for mde in [0.2, 0.3, 0.4, 0.5]:
    n = sample_size_two_sample(baseline_std, mde, ALPHA, TARGET_POWER) * deff
    mde_table[str(mde)] = int(round(n))

# duration at Olist's observed order volume
days = (delivered["order_purchase_timestamp"].max()
        - delivered["order_purchase_timestamp"].min()).days
orders_per_day = len(delivered) / days
late_per_day = orders_per_day * explor["late_rate"]
# customers with a late order per day (approx: late orders are ~1 per customer)
days_needed = (2 * per_arm_adj) / late_per_day

# OBF boundaries for the sequential plan
bounds, info_frac, spent = obf_boundaries(N_LOOKS, ALPHA)

# CUPED gate on real pre-treatment covariates (known at purchase time)
order_value = items.groupby("order_id")["price"].sum()
freight = items.groupby("order_id")["freight_value"].sum()
elig2 = eligible.set_index("order_id")
cuped_results = {}
for name, series in [("order_value", order_value), ("freight_value", freight)]:
    x = elig2.index.map(series).to_numpy(dtype=float)
    use_it, theta, reduction = cuped_gate(y, x)
    cuped_results[name] = {"use": bool(use_it), "theta": float(theta),
                           "variance_reduction": float(reduction)}

result = {
    "note": "All statistics measured from real Olist data. "
            "No treatment effect is assumed or claimed.",
    "eligible_customers_historical": n_eligible_hist,
    "baseline_review_mean_late": round(baseline_mean, 4),
    "baseline_review_std_late": round(baseline_std, 4),
    "mean_late_orders_per_customer": round(mean_cluster, 4),
    "within_customer_corr_measured": round(icc, 4),
    "design_effect": round(deff, 4),
    "alpha": ALPHA,
    "target_power": TARGET_POWER,
    "mde_stars": MDE_STARS,
    "sample_size_per_arm": int(round(per_arm_adj)),
    "total_sample_size": int(round(2 * per_arm_adj)),
    "mde_table_per_arm": mde_table,
    "olist_orders_per_day": round(orders_per_day, 1),
    "late_orders_per_day": round(late_per_day, 1),
    "estimated_days_to_enroll_at_olist_volume": round(days_needed, 1),
    "sequential_plan": {
        "n_looks": N_LOOKS,
        "method": "Lan-DeMets O'Brien-Fleming alpha spending",
        "info_fractions": [round(t, 3) for t in info_frac],
        "bounds": [round(b, 3) for b in bounds],
        "cumulative_alpha_spent": [round(s, 5) for s in spent],
    },
    "cuped_gate_results": cuped_results,
}
with open(OUT, "w") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2))
print("wrote", OUT)
