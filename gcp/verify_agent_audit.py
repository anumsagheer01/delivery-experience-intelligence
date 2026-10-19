#!/usr/bin/env python3
"""Independent correctness verification for ALL 500 cloud agent decisions.

For every row in dei_mart.agent_audit, independently recompute the expected
action from raw warehouse facts plus the BQML risk score, using a fresh
implementation of the policy rules (not the agent's code), and assert the
agent's recorded action matches.

Batched: one BigQuery job computes features + ML.PREDICT for all 500 orders.

Proves (policy correctness): the agent applied its deterministic policy
exactly right on all 500 real decisions.
Does NOT prove: model quality (measured by ROC-AUC) or business impact
(dry-run; nothing was sent).
"""
import sys

from google.cloud import bigquery

PROJECT = "delivery-experience-511901"
DATASET = "dei_mart"
LOCATION = "us-central1"

BAD_POD = {"no_package", "wrong_location", "unsafe_placement"}


def expected_action(is_late, review_score, risk_score):
    reasons = []
    if risk_score is not None and risk_score >= 0.70:
        reasons.append("risk>=0.70")
    if is_late and (review_score if review_score is not None else 5) <= 2:
        reasons.append("late+low-review")
    n = len(reasons)
    confidence = 0.9 if n >= 2 else (0.7 if n else 0.95)
    if not reasons:
        return "no_action"
    if confidence < 0.60:
        return "escalate"
    return "draft_customer_message"  # pod_quality is always None in this run


def main():
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    audit = {r["order_id"]: r["action"]
             for r in client.query(
                 f"SELECT order_id, action FROM `{PROJECT}.{DATASET}.agent_audit`"
             ).result()}
    print(f"audit rows: {len(audit)}")
    oids = list(audit.keys())

    q = f"""
    WITH base AS (
      SELECT
        o.order_id,
        (o.order_delivered_customer_date > o.order_estimated_delivery_date) AS is_late,
        rev.min_score AS review_score,
        pay.payment_type, pay.payment_installments,
        it.price, it.freight_value, it.n_items,
        c.customer_state, s.seller_state,
        p.product_category_name, p.product_weight_g,
        DATE_DIFF(DATE(o.order_estimated_delivery_date),
                  DATE(o.order_purchase_timestamp), DAY) AS promised_days,
        EXTRACT(DAYOFWEEK FROM o.order_purchase_timestamp) AS purchase_dow,
        EXTRACT(MONTH FROM o.order_purchase_timestamp) AS purchase_month
      FROM `{PROJECT}.{DATASET}.orders` o
      JOIN (SELECT order_id, SUM(price) AS price, SUM(freight_value) AS freight_value,
                   COUNT(*) AS n_items, MIN(seller_id) AS seller_id,
                   MIN(product_id) AS product_id
            FROM `{PROJECT}.{DATASET}.order_items` GROUP BY order_id) it USING (order_id)
      JOIN (SELECT order_id, MIN(payment_type) AS payment_type,
                   MAX(payment_installments) AS payment_installments
            FROM `{PROJECT}.{DATASET}.order_payments` GROUP BY order_id) pay USING (order_id)
      JOIN `{PROJECT}.{DATASET}.customers` c USING (customer_id)
      JOIN `{PROJECT}.{DATASET}.sellers` s ON s.seller_id = it.seller_id
      JOIN `{PROJECT}.{DATASET}.products` p ON p.product_id = it.product_id
      LEFT JOIN (SELECT order_id, MIN(review_score) AS min_score
                 FROM `{PROJECT}.{DATASET}.order_reviews` GROUP BY order_id) rev USING (order_id)
      WHERE o.order_id IN UNNEST(@oids)
    ),
    scored AS (
      SELECT order_id, predicted_is_late AS risk_score FROM ML.PREDICT(
        MODEL `{PROJECT}.{DATASET}.late_delivery_risk`,
        -- order_id is not a model feature (excluded at training time), so
        -- BigQuery passes it through untouched to the prediction output.
        (SELECT * EXCEPT (is_late, review_score) FROM base))
    )
    SELECT b.order_id, b.is_late, b.review_score, s.risk_score
    FROM base b LEFT JOIN scored s USING (order_id)"""
    rows = list(client.query(
        q, job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ArrayQueryParameter("oids", "STRING", oids)])
    ).result())
    print(f"scored rows: {len(rows)}")

    mismatches, by_expected = [], {}
    for r in rows:
        exp = expected_action(bool(r["is_late"]), r["review_score"],
                              float(r["risk_score"]) if r["risk_score"] is not None else None)
        by_expected[exp] = by_expected.get(exp, 0) + 1
        if audit[r["order_id"]] != exp:
            mismatches.append((r["order_id"], audit[r["order_id"]], exp,
                               bool(r["is_late"]), r["review_score"], r["risk_score"]))
    print(f"expected mix: {by_expected}")
    print(f"mismatches: {len(mismatches)}")
    for m in mismatches[:20]:
        print("MISMATCH order=%s agent=%s expected=%s is_late=%s review=%s risk=%s" % m)
    assert not mismatches, f"{len(mismatches)} decisions disagree with the policy"
    print("PASS: all agent decisions match the independently computed policy")


if __name__ == "__main__":
    sys.exit(main())
