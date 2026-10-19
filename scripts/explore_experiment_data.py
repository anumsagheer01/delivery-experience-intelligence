"""Exploration for the customer-outreach A/B test design.

Computes, from real Olist data only:
  - orders per customer (customer_unique_id) distribution
  - late-order flag rate and review-score mean/std among late orders
  - within-customer correlation of review scores (ICC proxy)
  - correlation of pre-treatment covariates with review_score (CUPED screen)

Writes results to evals/experiments/data_exploration.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

RAW = os.path.expanduser("~/workspace/build/data/raw/olist")
OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "evals", "experiments", "data_exploration.json",
)
os.makedirs(os.path.dirname(OUT), exist_ok=True)

orders = pd.read_csv(os.path.join(RAW, "olist_orders_dataset.csv"))
customers = pd.read_csv(os.path.join(RAW, "olist_customers_dataset.csv"))
reviews = pd.read_csv(os.path.join(RAW, "olist_order_reviews_dataset.csv"))
items = pd.read_csv(os.path.join(RAW, "olist_order_items_dataset.csv"))
payments = pd.read_csv(os.path.join(RAW, "olist_order_payments_dataset.csv"))

# Late flag: delivered after estimated delivery date (delivered orders only)
for c in ["order_delivered_customer_date", "order_estimated_delivery_date",
          "order_purchase_timestamp"]:
    orders[c] = pd.to_datetime(orders[c], errors="coerce")
delivered = orders[orders["order_status"] == "delivered"].copy()
delivered["is_late"] = (
    delivered["order_delivered_customer_date"]
    > delivered["order_estimated_delivery_date"]
)

# Attach unique customer id
cust_map = customers[["customer_id", "customer_unique_id"]]
delivered = delivered.merge(cust_map, on="customer_id", how="left")

# Orders per customer
per_cust = delivered.groupby("customer_unique_id").size()
multi = (per_cust > 1).mean()

# Reviews: keep earliest review per order, join late flag + customer
reviews["review_creation_date"] = pd.to_datetime(
    reviews["review_creation_date"], errors="coerce")
reviews = reviews.sort_values("review_creation_date").drop_duplicates(
    "order_id", keep="first")
rev = reviews[["order_id", "review_score"]].merge(
    delivered[["order_id", "is_late", "customer_unique_id",
               "order_purchase_timestamp"]],
    on="order_id", how="inner")

late_rev = rev[rev["is_late"]]["review_score"]
all_rev = rev["review_score"]

# ICC proxy: correlation between a customer's first and second order scores
cust_scores = rev.sort_values("order_purchase_timestamp").groupby(
    "customer_unique_id")["review_score"].apply(list)
pairs = [s[:2] for s in cust_scores if len(s) >= 2]
icc = float(np.corrcoef([p[0] for p in pairs], [p[1] for p in pairs])[0, 1]) \
    if len(pairs) > 100 else None

# Covariate screen for CUPED: order value, freight, state, category, payment
order_value = items.groupby("order_id")["price"].sum().rename("order_value")
freight = items.groupby("order_id")["freight_value"].sum().rename("freight")
products = pd.read_csv(os.path.join(RAW, "olist_products_dataset.csv"))[
    ["product_id", "product_category_name"]]
items = items.merge(products, on="product_id", how="left")
cat = items.sort_values("order_item_id").drop_duplicates("order_id")[
    ["order_id", "product_category_name"]]
pay = payments.sort_values("payment_sequential").drop_duplicates("order_id")[
    ["order_id", "payment_type"]]
state = customers[["customer_id", "customer_state"]]
feat = rev.merge(order_value, on="order_id", how="left") \
          .merge(freight, on="order_id", how="left") \
          .merge(cat, on="order_id", how="left") \
          .merge(pay, on="order_id", how="left") \
          .merge(state, left_on="customer_id", right_on="customer_id",
                 how="left") if "customer_id" in rev.columns else None
if feat is None:
    feat = rev.merge(order_value, on="order_id", how="left") \
              .merge(freight, on="order_id", how="left") \
              .merge(cat, on="order_id", how="left") \
              .merge(pay, on="order_id", how="left")
    tmp = delivered[["order_id", "customer_id"]].merge(
        customers[["customer_id", "customer_state"]], on="customer_id",
        how="left")
    feat = feat.merge(tmp[["order_id", "customer_state"]], on="order_id",
                      how="left")

num_corr = {}
for col in ["order_value", "freight"]:
    s = feat[[col, "review_score"]].dropna()
    num_corr[col] = float(s[col].corr(s["review_score"])) if len(s) > 100 else None

cat_corr = {}
for col in ["product_category_name", "payment_type", "customer_state"]:
    g = feat.dropna(subset=[col]).groupby(col)["review_score"]
    if g.ngroups >= 5:
        # eta-squared: between-group SS / total SS
        overall = feat["review_score"].mean()
        ss_between = ((g.mean() - overall) ** 2 * g.size()).sum()
        ss_total = ((feat["review_score"] - overall) ** 2).sum()
        cat_corr[col] = float(ss_between / ss_total)

result = {
    "n_delivered_orders": int(len(delivered)),
    "n_unique_customers": int(delivered["customer_unique_id"].nunique()),
    "late_rate": float(delivered["is_late"].mean()),
    "share_customers_with_gt1_order": float(multi),
    "orders_per_customer_p50": float(per_cust.median()),
    "orders_per_customer_p99": float(per_cust.quantile(0.99)),
    "n_reviews_total": int(len(all_rev)),
    "n_reviews_late_orders": int(len(late_rev)),
    "review_mean_all": float(all_rev.mean()),
    "review_std_all": float(all_rev.std()),
    "review_mean_late": float(late_rev.mean()),
    "review_std_late": float(late_rev.std()),
    "within_customer_score_corr_n_pairs": int(len(pairs)),
    "within_customer_score_corr": icc,
    "numeric_covariate_corr_with_review": num_corr,
    "categorical_eta_squared_with_review": cat_corr,
}
with open(OUT, "w") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2))
print("wrote", OUT)
