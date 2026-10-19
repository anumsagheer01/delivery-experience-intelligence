"""Calibrate per-arm sample size for 80% OBF power under the ceiling model.

The review score is bounded in [1,5] with 22.3% of late-order reviews already
at 5 (measured). A hypothetical +0.3 star shift therefore realizes as +0.233
on average. This script finds, by simulation on real historical outcomes,
the per-arm n at which the O'Brien-Fleming plan reaches 80% power for that
realizable shift. Pure simulation; no uplift is claimed.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from src.experiments.analysis import sequential_decision, welch_ttest
from src.experiments.assignment import assign
from src.experiments.design import ALPHA, EXPERIMENT_ID, MDE_STARS, N_LOOKS

RAW = os.path.expanduser("~/workspace/build/data/raw/olist")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

orders = pd.read_csv(os.path.join(RAW, "olist_orders_dataset.csv"))
customers = pd.read_csv(os.path.join(RAW, "olist_customers_dataset.csv"))
reviews = pd.read_csv(os.path.join(RAW, "olist_order_reviews_dataset.csv"))
for c in ["order_delivered_customer_date", "order_estimated_delivery_date",
          "order_purchase_timestamp"]:
    orders[c] = pd.to_datetime(orders[c], errors="coerce")
d = orders[orders["order_status"] == "delivered"].copy()
d["is_late"] = (d["order_delivered_customer_date"]
                > d["order_estimated_delivery_date"])
d = d.merge(customers[["customer_id", "customer_unique_id"]],
            on="customer_id")
reviews["review_creation_date"] = pd.to_datetime(
    reviews["review_creation_date"], errors="coerce")
reviews = reviews.sort_values("review_creation_date").drop_duplicates(
    "order_id")
late = d[d["is_late"]].merge(reviews[["order_id", "review_score"]],
                             on="order_id")
elig = late.sort_values("order_purchase_timestamp").drop_duplicates(
    "customer_unique_id").reset_index(drop=True)
uids = elig["customer_unique_id"].to_numpy()
y_all = elig["review_score"].to_numpy(dtype=float)

with open(os.path.join(ROOT, "evals", "experiments",
                       "power_analysis.json")) as f:
    bounds = json.load(f)["sequential_plan"]["bounds"]

rng = np.random.default_rng(11)
N_SEEDS = 300


def power_at(per_arm):
    n = 2 * per_arm
    hits = 0
    for s in range(N_SEEDS):
        pick = rng.integers(0, len(uids), n)
        arms = [assign(f"cal{s}:{u}", salt="replay",
                       experiment_id=EXPERIMENT_ID)
                for u in uids[pick]]
        is_t = np.array([a == "treatment" for a in arms])
        y = y_all[pick].copy()
        y[is_t] = np.clip(y[is_t] + MDE_STARS, 1, 5)
        chunks = np.array_split(np.arange(n), N_LOOKS)
        zs, idx = [], np.array([], dtype=int)
        for ch in chunks:
            idx = np.concatenate([idx, ch])
            r = welch_ttest(y[idx][is_t[idx]], y[idx][~is_t[idx]],
                            alpha=ALPHA)
            zs.append(r["t_stat"])
        if any(dd["decision"] == "reject"
               for dd in sequential_decision(zs, bounds)):
            hits += 1
    return hits / N_SEEDS


results = {}
for per_arm in [482, 650, 800, 950]:
    p = power_at(per_arm)
    results[per_arm] = round(p, 3)
    print(f"per_arm={per_arm}: OBF power={p:.3f}", flush=True)

OUT = os.path.join(ROOT, "evals", "experiments",
                   "sample_size_calibration.json")
with open(OUT, "w") as f:
    json.dump({
        "note": "Simulation on real outcomes; effect is SIMULATED (+0.3 "
                "stars clipped to [1,5], realized +0.233).",
        "target_power": 0.80,
        "power_by_per_arm_n": {str(k): v for k, v in results.items()},
    }, f, indent=2)
print("wrote", OUT)
