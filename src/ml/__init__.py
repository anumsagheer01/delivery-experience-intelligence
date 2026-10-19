"""Delivery risk models: late-delivery and low-review classifiers.

Methodology (the parts interviewers probe):
- Temporal split: train on orders purchased before 2018-01-01, test after.
  Random splits leak the future (seasonality, ops changes).
- Purchase-time features ONLY: nothing observed after dispatch. Using the
  actual delivery date as a feature would be target leakage.
- Baselines first: dummy (stratified) then logistic regression, then
  gradient boosting. Report ROC-AUC, PR-AUC, precision/recall/F1,
  calibration, and feature importance.
"""
import os

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ..logging import get_logger

log = get_logger(__name__)

TRAIN_CUTOFF = "2018-01-01"


def build_features(olist_dir: str) -> pd.DataFrame:
    orders = pd.read_csv(f"{olist_dir}/olist_orders_dataset.csv",
                         parse_dates=["order_purchase_timestamp",
                                      "order_delivered_customer_date",
                                      "order_estimated_delivery_date"])
    items = pd.read_csv(f"{olist_dir}/olist_order_items_dataset.csv")
    pay = pd.read_csv(f"{olist_dir}/olist_order_payments_dataset.csv")
    cust = pd.read_csv(f"{olist_dir}/olist_customers_dataset.csv")
    sell = pd.read_csv(f"{olist_dir}/olist_sellers_dataset.csv")
    prod = pd.read_csv(f"{olist_dir}/olist_products_dataset.csv")
    rev = pd.read_csv(f"{olist_dir}/olist_order_reviews_dataset.csv")

    df = orders[orders.order_status == "delivered"].copy()
    df = df.dropna(subset=["order_delivered_customer_date",
                           "order_estimated_delivery_date"])
    df["is_late"] = (df.order_delivered_customer_date
                     > df.order_estimated_delivery_date).astype(int)

    g = items.groupby("order_id").agg(price=("price", "sum"),
                                      freight_value=("freight_value", "sum"),
                                      n_items=("order_item_id", "count"),
                                      seller_id=("seller_id", "first"),
                                      product_id=("product_id", "first"))
    df = df.join(g, on="order_id")
    df = df.join(pay.groupby("order_id").agg(
        payment_type=("payment_type", "first"),
        payment_installments=("payment_installments", "max")), on="order_id")
    df = df.join(cust.set_index("customer_id")[["customer_state"]], on="customer_id")
    df = df.join(sell.set_index("seller_id")[["seller_state"]], on="seller_id")
    df = df.join(prod.set_index("product_id")[
        ["product_category_name", "product_weight_g"]], on="product_id")
    df = df.join(rev.groupby("order_id")["review_score"].min()
               .rename("review_score"), on="order_id")
    df["is_low_review"] = (df.review_score <= 2).astype(int)

    df["promised_days"] = (df.order_estimated_delivery_date
                           - df.order_purchase_timestamp).dt.days
    df["purchase_dow"] = df.order_purchase_timestamp.dt.dayofweek
    df["purchase_month"] = df.order_purchase_timestamp.dt.month
    return df


FEATURES = ["price", "freight_value", "n_items", "payment_installments",
            "product_weight_g", "promised_days", "purchase_dow", "purchase_month",
            "payment_type", "customer_state", "seller_state", "product_category_name"]
NUM = ["price", "freight_value", "n_items", "payment_installments",
       "product_weight_g", "promised_days", "purchase_dow", "purchase_month"]
CAT = ["payment_type", "customer_state", "seller_state", "product_category_name"]


def make_pipeline(model):
    pre = ColumnTransformer([
        ("num", StandardScaler(), NUM),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=50,
                          sparse_output=False), CAT),
    ])
    return Pipeline([("pre", pre), ("clf", model)])


def evaluate(name, y_true, proba, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    # threshold sweep: 0.5 is arbitrary under class imbalance; report best-F1 too
    best = {"f1": -1}
    for t in [round(x, 2) for x in np.arange(0.05, 0.96, 0.05)]:
        p = (proba >= t).astype(int)
        f1 = f1_score(y_true, p, zero_division=0)
        if f1 > best["f1"]:
            best = {"threshold": t, "f1": round(float(f1), 4),
                    "precision": round(float(precision_score(y_true, p, zero_division=0)), 4),
                    "recall": round(float(recall_score(y_true, p, zero_division=0)), 4)}
    pred = (proba >= 0.5).astype(int)
    metrics = {
        "model": name,
        "n": int(len(y_true)),
        "positive_rate": round(float(y_true.mean()), 4),
        "roc_auc": round(float(roc_auc_score(y_true, proba)), 4),
        "pr_auc": round(float(average_precision_score(y_true, proba)), 4),
        "precision": round(float(precision_score(y_true, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, pred, zero_division=0)), 4),
        "brier": round(float(brier_score_loss(y_true, proba)), 4),
        "best_threshold": best,
        "confusion_matrix": confusion_matrix(y_true, pred).tolist(),
    }
    prob_true, prob_pred = calibration_curve(y_true, proba, n_bins=10)
    metrics["calibration"] = {
        "prob_true": [round(float(x), 3) for x in prob_true],
        "prob_pred": [round(float(x), 3) for x in prob_pred],
    }
    import json
    with open(f"{out_dir}/{name}.json", "w") as f:
        json.dump(metrics, f, indent=2)
    log.info("%s: %s", name, {k: v for k, v in metrics.items()
                              if k not in ("confusion_matrix", "calibration")})
    return metrics


def train_all(olist_dir: str, out_dir: str) -> dict:
    df = build_features(olist_dir).dropna(subset=FEATURES)
    train = df[df.order_purchase_timestamp < TRAIN_CUTOFF]
    test = df[df.order_purchase_timestamp >= TRAIN_CUTOFF]
    log.info("train=%d test=%d (cutoff %s)", len(train), len(test), TRAIN_CUTOFF)
    Xtr, Xte = train[FEATURES], test[FEATURES]
    results = {}
    for label in ["is_late", "is_low_review"]:
        ytr, yte = train[label].dropna(), test[label].dropna()
        common = yte.index.intersection(Xte.index)
        Xte_l, yte_l = Xte.loc[common], yte.loc[common]
        for mname, model in [
            ("dummy", DummyClassifier(strategy="stratified", random_state=42)),
            ("logreg", LogisticRegression(max_iter=2000)),
            ("hgb", HistGradientBoostingClassifier(random_state=42)),
        ]:
            pipe = make_pipeline(model)
            pipe.fit(Xtr.loc[ytr.index], ytr)
            proba = pipe.predict_proba(Xte_l)[:, 1]
            results[f"{label}__{mname}"] = evaluate(
                f"{label}__{mname}", yte_l.values, proba,
                f"{out_dir}/{label}")
    return results
