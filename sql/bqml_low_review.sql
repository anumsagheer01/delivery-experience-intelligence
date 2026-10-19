-- BigQuery ML: low-review risk, trained on real Olist data in BigQuery.
-- Label: min review_score <= 2 per order (mirrors src/ml/__init__.py).
-- Same purchase-time features and temporal split as the late-delivery model.
-- Orders without any review are excluded from training (label undefined).
-- Dataset: delivery-experience-511901.dei_mart (us-central1).
-- Executed in Cloud Shell on 2026-10-17. See evals/risk/bqml/ for measured metrics.

CREATE OR REPLACE MODEL `delivery-experience-511901.dei_mart.low_review_risk`
OPTIONS(model_type='BOOSTED_TREE_CLASSIFIER',
        input_label_cols=['is_low_review'],
        max_tree_depth=6,
        learn_rate=0.1,
        data_split_method='NO_SPLIT') AS
WITH base AS (
  SELECT
    o.order_id,
    o.order_purchase_timestamp,
    CASE WHEN rev.min_score <= 2 THEN 1 ELSE 0 END AS is_low_review,
    pay.payment_type,
    pay.payment_installments,
    it.price,
    it.freight_value,
    it.n_items,
    c.customer_state,
    s.seller_state,
    p.product_category_name,
    p.product_weight_g,
    DATE_DIFF(DATE(o.order_estimated_delivery_date),
              DATE(o.order_purchase_timestamp), DAY) AS promised_days,
    EXTRACT(DAYOFWEEK FROM o.order_purchase_timestamp) AS purchase_dow,
    EXTRACT(MONTH FROM o.order_purchase_timestamp) AS purchase_month
  FROM `delivery-experience-511901.dei_mart.orders` o
  JOIN (
    SELECT order_id, SUM(price) AS price, SUM(freight_value) AS freight_value,
           COUNT(*) AS n_items, MIN(seller_id) AS seller_id, MIN(product_id) AS product_id
    FROM `delivery-experience-511901.dei_mart.order_items`
    GROUP BY order_id
  ) it USING (order_id)
  JOIN (
    SELECT order_id, MIN(payment_type) AS payment_type,
           MAX(payment_installments) AS payment_installments
    FROM `delivery-experience-511901.dei_mart.order_payments`
    GROUP BY order_id
  ) pay USING (order_id)
  JOIN `delivery-experience-511901.dei_mart.customers` c USING (customer_id)
  JOIN `delivery-experience-511901.dei_mart.sellers` s ON s.seller_id = it.seller_id
  JOIN `delivery-experience-511901.dei_mart.products` p ON p.product_id = it.product_id
  JOIN (
    SELECT order_id, MIN(review_score) AS min_score
    FROM `delivery-experience-511901.dei_mart.order_reviews`
    GROUP BY order_id
  ) rev USING (order_id)
  WHERE o.order_status = 'delivered'
    AND o.order_delivered_customer_date IS NOT NULL
    AND o.order_estimated_delivery_date IS NOT NULL
    AND o.order_purchase_timestamp < '2018-01-01'
)
SELECT * EXCEPT (order_id, order_purchase_timestamp)
FROM base
WHERE price IS NOT NULL AND freight_value IS NOT NULL AND n_items IS NOT NULL
  AND payment_installments IS NOT NULL AND product_weight_g IS NOT NULL
  AND promised_days IS NOT NULL AND purchase_dow IS NOT NULL AND purchase_month IS NOT NULL
  AND payment_type IS NOT NULL AND customer_state IS NOT NULL AND seller_state IS NOT NULL
  AND product_category_name IS NOT NULL;
