"""Cloud context builder: enrich a streaming event with BigQuery facts.

For a DELIVERED (or any) event carrying an order_id, this builds the agent
context dict from the cloud warehouse:
  order      : real order facts (status, is_late, min review score)
  risk_score : predicted late-delivery probability from the BQML model
               (ML.PREDICT on dei_mart.late_delivery_risk)
  pod_quality: filled by the vision path (see attach_pod_quality) when a
               POD photo assessment exists for the order; None otherwise.

Runs in Cloud Shell (needs GCP credentials); the agent policy itself
(src/agents/__init__.py) is unchanged. See scripts/e2e_agent_cloud.py.
"""
from google.cloud import bigquery

PROJECT = "delivery-experience-511901"
DATASET = "dei_mart"
LOCATION = "us-central1"

FEATURE_SQL = """
WITH base AS (
  SELECT
    o.order_id,
    CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date
         THEN 1 ELSE 0 END AS is_late,
    rev.min_score AS review_score,
    pay.payment_type, pay.payment_installments,
    it.price, it.freight_value, it.n_items,
    c.customer_state, s.seller_state,
    p.product_category_name, p.product_weight_g,
    DATE_DIFF(DATE(o.order_estimated_delivery_date),
              DATE(o.order_purchase_timestamp), DAY) AS promised_days,
    EXTRACT(DAYOFWEEK FROM o.order_purchase_timestamp) AS purchase_dow,
    EXTRACT(MONTH FROM o.order_purchase_timestamp) AS purchase_month
  FROM `delivery-experience-511901.dei_mart.orders` o
  JOIN (SELECT order_id, SUM(price) AS price, SUM(freight_value) AS freight_value,
               COUNT(*) AS n_items, MIN(seller_id) AS seller_id,
               MIN(product_id) AS product_id
        FROM `delivery-experience-511901.dei_mart.order_items` GROUP BY order_id
  ) it USING (order_id)
  JOIN (SELECT order_id, MIN(payment_type) AS payment_type,
               MAX(payment_installments) AS payment_installments
        FROM `delivery-experience-511901.dei_mart.order_payments` GROUP BY order_id
  ) pay USING (order_id)
  JOIN `delivery-experience-511901.dei_mart.customers` c USING (customer_id)
  JOIN `delivery-experience-511901.dei_mart.sellers` s ON s.seller_id = it.seller_id
  JOIN `delivery-experience-511901.dei_mart.products` p ON p.product_id = it.product_id
  LEFT JOIN (SELECT order_id, MIN(review_score) AS min_score
             FROM `delivery-experience-511901.dei_mart.order_reviews`
             GROUP BY order_id) rev USING (order_id)
  WHERE o.order_id = @order_id
)
SELECT * EXCEPT (order_id) FROM base
"""


def build_context(order_id: str, client: bigquery.Client = None) -> dict:
    """Return the agent context dict for one order_id from BigQuery."""
    client = client or bigquery.Client(project=PROJECT, location=LOCATION)
    job = client.query(
        FEATURE_SQL,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("order_id", "STRING", order_id)
            ]
        ),
    )
    rows = list(job.result())
    if not rows:
        return {"order": None, "risk_score": None, "pod_quality": None}
    r = dict(rows[0])
    is_late = r.pop("is_late")
    review_score = r.pop("review_score")

    pred_sql = (
        "SELECT predicted_is_late AS risk FROM ML.PREDICT("
        "MODEL `delivery-experience-511901.dei_mart.late_delivery_risk`, (%s))"
        % FEATURE_SQL.replace("@order_id", "'%s'" % order_id.replace("'", ""))
    )
    try:
        prow = list(client.query(pred_sql).result())
        risk = float(prow[0]["risk"]) if prow else None
    except Exception:
        risk = None

    return {
        "order": {"is_late": bool(is_late), "review_score": review_score},
        "risk_score": risk,
        "pod_quality": None,
    }


def attach_pod_quality(context: dict, gcs_uri: str, assessor) -> dict:
    """Fill context["pod_quality"] from a vision PodAssessor.

    assessor: src.vision.automl.PodAssessor loaded with batch prediction
    results. When no batch result exists for gcs_uri, pod_quality stays
    None (unknown), which the policy treats as "no photo evidence",
    never as a negative signal.
    """
    result = assessor.assess(gcs_uri)
    if result["assessed"]:
        context["pod_quality"] = {
            "package_visible": result["package_visible"],
            "confidence": result["confidence"],
            "source": "automl:dei-pod-automl-v1",
        }
    return context
