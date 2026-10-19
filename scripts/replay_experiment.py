"""Historical replay of the outreach experiment (SIMULATED treatment effects).

Uses REAL Olist customers, REAL review scores, and REAL deterministic
assignment. Only the treatment effect is simulated: treatment-arm outcomes
are shifted by a hypothetical delta (clipped to the 1-5 review range).

Purpose: validate the analysis pipeline end to end:
  1. Under delta = 0 (null), the O'Brien-Fleming plan must hold the
     family-wise type I error near 0.05, while naive repeated testing
     must show the expected inflation (the peeking problem, demonstrated).
  2. Under delta = +0.3 stars, empirical power must land near the designed
     0.80.

Nothing here measures a real uplift. No uplift is claimed anywhere.

Writes evals/experiments/replay_results.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from src.experiments.analysis import sequential_decision, welch_ttest
from src.experiments.assignment import assign
from src.experiments.design import (ALPHA, EXPERIMENT_ID, MDE_STARS, N_LOOKS)

SIMULATED_LABEL = (
    "SIMULATED treatment effect on real historical outcomes. "
    "Not a measured uplift."
)

RAW = os.path.expanduser("~/workspace/build/data/raw/olist")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "evals", "experiments", "replay_results.json")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

orders = pd.read_csv(os.path.join(RAW, "olist_orders_dataset.csv"))
customers = pd.read_csv(os.path.join(RAW, "olist_customers_dataset.csv"))
reviews = pd.read_csv(os.path.join(RAW, "olist_order_reviews_dataset.csv"))

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
eligible = late.drop_duplicates("customer_unique_id", keep="first").copy()
eligible["arm"] = eligible["customer_unique_id"].apply(
    lambda u: assign(u, salt="replay", experiment_id=EXPERIMENT_ID))
base = eligible[["customer_unique_id", "arm", "review_score",
                 "order_purchase_timestamp"]].reset_index(drop=True)

with open(os.path.join(ROOT, "evals", "experiments",
                       "power_analysis.json")) as f:
    power_cfg = json.load(f)
bounds = power_cfg["sequential_plan"]["bounds"]

N_SEEDS = 500
DESIGNED_N = 2 * power_cfg["sample_size_per_arm"]  # 964, the designed size
rng = np.random.default_rng(7)


def run_once(df, delta, seed):
    """One simulated experiment at the designed sample size.

    Fresh randomness per seed: bootstrap-resample customers with replacement
    and re-randomize arms with a seed salt (assignment stays a pure,
    deterministic function within each seed). Under delta=0 this is a true
    null, so the rejection rate estimates the family-wise type I error.
    Returns (obf_rejected, naive_rejected, stopped_look).
    """
    pick = rng.integers(0, len(df), DESIGNED_N)
    d = df.iloc[pick].reset_index(drop=True)
    arms = [assign(f"{seed}:{u}", salt="replay",
                   experiment_id=EXPERIMENT_ID) for u in d["customer_unique_id"]]
    is_t = np.array([a == "treatment" for a in arms])
    y = d["review_score"].to_numpy(dtype=float)
    y_sim = y.copy()
    y_sim[is_t] = np.clip(y_sim[is_t] + delta, 1, 5)
    chunks = np.array_split(np.arange(DESIGNED_N), N_LOOKS)
    z_stats, naive_ps = [], []
    idx = np.array([], dtype=int)
    for ch in chunks:
        idx = np.concatenate([idx, ch])
        r = welch_ttest(y_sim[idx][is_t[idx]], y_sim[idx][~is_t[idx]],
                        alpha=ALPHA)
        z_stats.append(r["t_stat"])
        naive_ps.append(r["p_value"])
    dec = sequential_decision(z_stats, bounds)
    obf_reject = any(dd["decision"] == "reject" for dd in dec)
    naive_reject = any(p < ALPHA for p in naive_ps)
    stopped_look = next((dd["look"] for dd in dec
                         if dd["decision"] == "reject"), None)
    return obf_reject, naive_reject, stopped_look


scenarios = {}
for delta in [0.0, MDE_STARS]:
    obf_hits = naive_hits = 0
    stop_looks = []
    for s in range(N_SEEDS):
        obf_r, naive_r, look = run_once(base, delta, seed=s)
        obf_hits += obf_r
        naive_hits += naive_r
        if obf_r:
            stop_looks.append(look)
    key = "null_delta_0" if delta == 0 else f"effect_plus_{delta}_stars"
    scenarios[key] = {
        "simulated_delta_stars": delta,
        "seeds": N_SEEDS,
        "obf_family_wise_rejection_rate": round(obf_hits / N_SEEDS, 4),
        "naive_repeated_testing_rejection_rate": round(naive_hits / N_SEEDS, 4),
        "mean_stopping_look_when_rejected": (
            round(float(np.mean(stop_looks)), 2) if stop_looks else None),
    }

def walkthrough(seed):
    """Run one full sequential walk-through; return (looks, final_diff)."""
    rng_w = np.random.default_rng(seed)
    pick = rng_w.integers(0, len(base), DESIGNED_N)
    dd = base.iloc[pick].reset_index(drop=True)
    arms = [assign(f"detail{seed}:{u}", salt="replay",
                   experiment_id=EXPERIMENT_ID)
            for u in dd["customer_unique_id"]]
    is_t = np.array([a == "treatment" for a in arms])
    y = dd["review_score"].to_numpy(dtype=float)
    y_sim = y.copy()
    y_sim[is_t] = np.clip(y_sim[is_t] + MDE_STARS, 1, 5)
    chunks = np.array_split(np.arange(DESIGNED_N), N_LOOKS)
    looks, idx = [], np.array([], dtype=int)
    for k, ch in enumerate(chunks):
        idx = np.concatenate([idx, ch])
        r = welch_ttest(y_sim[idx][is_t[idx]], y_sim[idx][~is_t[idx]],
                        alpha=ALPHA)
        looks.append({
            "look": k + 1,
            "n_total": int(len(idx)),
            "diff_stars": round(r["diff"], 3),
            "ci_low": round(r["ci_low"], 3),
            "ci_high": round(r["ci_high"], 3),
            "p_value": round(r["p_value"], 5),
            "obf_bound": bounds[k],
            "obf_decision": sequential_decision(
                [r["t_stat"]], [bounds[k]])[0]["decision"],
        })
    return looks, looks[-1]["diff_stars"]


# Representative walk-through: the seed whose final estimate sits at the
# median across candidates (typical trajectory, not a selected winner).
cands = [(s, walkthrough(s)) for s in range(25)]
cands.sort(key=lambda c: c[1][1])
detail_looks = cands[len(cands) // 2][1][0]
detail_seed = cands[len(cands) // 2][0]

arm_counts = base["arm"].value_counts().to_dict()

result = {
    "label": SIMULATED_LABEL,
    "n_eligible_customers_historical": int(len(base)),
    "simulated_experiment_size": int(DESIGNED_N),
    "arm_counts_historical_deterministic_assignment": {
        k: int(v) for k, v in arm_counts.items()},
    "alpha": ALPHA,
    "n_looks": N_LOOKS,
    "scenarios": scenarios,
    "detailed_walkthrough_simulated_plus_0.3": detail_looks,
    "walkthrough_seed_median_of_25": int(detail_seed),
    "reading": {
        "null": "OBF rejection rate sits near 0.05 (type I error controlled); "
                "naive repeated testing inflates to about 0.13, demonstrating "
                "the peeking problem.",
        "effect": "At the textbook 482/arm, OBF power is about 0.60, not "
                  "0.80, because the 1-5 ceiling attenuates a +0.3 shift to "
                  "+0.233 realized. See sample_size_calibration.json: about "
                  "730/arm reaches 80% OBF power under the ceiling model.",
    },
}
with open(OUT, "w") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2))
print("wrote", OUT)
