-- Dashboard views for Looker Studio, targeting the real dei_mart dataset.
-- Project: delivery-experience-511901, location us-central1.
-- Run in Cloud Shell: bq query --nouse_legacy_sql < sql/dashboard_views.sql
-- (or paste into the BigQuery console). All views are read-only over
-- real tables; nothing here trains models or moves data.

-- 1. Late-delivery rate by customer state (matches dashboard preview chart).
CREATE OR REPLACE VIEW `delivery-experience-511901.dei_mart.v_late_by_state` AS
SELECT c.customer_state AS state, COUNT(*) AS orders,
       ROUND(AVG(CASE WHEN o.order_delivered_customer_date
                          > o.order_estimated_delivery_date
                     THEN 1 ELSE 0 END), 4) AS late_rate
FROM `delivery-experience-511901.dei_mart.orders` o
JOIN `delivery-experience-511901.dei_mart.customers` c USING (customer_id)
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
  AND o.order_estimated_delivery_date IS NOT NULL
GROUP BY state ORDER BY late_rate DESC;

-- 2. Average review score by lateness.
CREATE OR REPLACE VIEW `delivery-experience-511901.dei_mart.v_late_vs_reviews` AS
WITH d AS (
  SELECT o.order_id,
         o.order_delivered_customer_date > o.order_estimated_delivery_date
           AS is_late,
         r.review_score
  FROM `delivery-experience-511901.dei_mart.orders` o
  JOIN `delivery-experience-511901.dei_mart.order_reviews` r USING (order_id)
  WHERE o.order_status = 'delivered'
    AND o.order_delivered_customer_date IS NOT NULL
    AND o.order_estimated_delivery_date IS NOT NULL
)
SELECT is_late, COUNT(*) AS orders,
       ROUND(AVG(review_score), 2) AS avg_review
FROM d GROUP BY is_late;

-- 3. Amazon last-mile: zone-revisit summary per route.
-- A "revisit" is a delivery zone the driver entered more than once.
CREATE OR REPLACE VIEW `delivery-experience-511901.dei_mart.v_zone_revisits` AS
WITH ordered AS (
  SELECT sq.route_id, st.zone_id
  FROM (
    SELECT route_id, stop_id
    FROM `delivery-experience-511901.dei_mart.amz_sequences`,
    UNNEST(actual_stops) AS stop_id
  ) sq
  JOIN `delivery-experience-511901.dei_mart.amz_stops` st
    ON st.route_id = sq.route_id AND st.stop_id = sq.stop_id
),
zone_counts AS (
  SELECT route_id, zone_id, COUNT(*) AS visits
  FROM ordered
  WHERE zone_id IS NOT NULL
  GROUP BY route_id, zone_id
),
revisits AS (
  SELECT route_id,
         COUNTIF(visits > 1) AS zones_revisited,
         SUM(IF(visits > 1, visits - 1, 0)) AS extra_zone_visits
  FROM zone_counts
  GROUP BY route_id
)
SELECT r.route_id, r.station_code,
       COALESCE(v.zones_revisited, 0) AS zones_revisited,
       COALESCE(v.extra_zone_visits, 0) AS extra_zone_visits
FROM `delivery-experience-511901.dei_mart.amz_routes` r
LEFT JOIN revisits v USING (route_id);

-- 4. BQML late-delivery risk scores on the temporal holdout
-- (sampled to ~10% so dashboard loads stay fast and cheap).
-- Same feature engineering and dropna filters as training.
CREATE OR REPLACE VIEW `delivery-experience-511901.dei_mart.v_risk_scores` AS
SELECT predicted_is_late AS risk_score
FROM ML.PREDICT(
  MODEL `delivery-experience-511901.dei_mart.late_delivery_risk`,
  (WITH base AS (
    SELECT
      o.order_id,
      o.order_purchase_timestamp,
      CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date
           THEN 1 ELSE 0 END AS is_late,
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
      SELECT order_id, SUM(price) AS price,
             SUM(freight_value) AS freight_value, COUNT(*) AS n_items,
             MIN(seller_id) AS seller_id, MIN(product_id) AS product_id
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
    JOIN `delivery-experience-511901.dei_mart.sellers` s
      ON s.seller_id = it.seller_id
    JOIN `delivery-experience-511901.dei_mart.products` p
      ON p.product_id = it.product_id
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
      AND o.order_estimated_delivery_date IS NOT NULL
      AND o.order_purchase_timestamp >= '2018-01-01'
      AND MOD(ABS(FARM_FINGERPRINT(o.order_id)), 10) = 0
  )
  SELECT * EXCEPT (order_id, order_purchase_timestamp)
  FROM base
  WHERE price IS NOT NULL AND freight_value IS NOT NULL AND n_items IS NOT NULL
    AND payment_installments IS NOT NULL AND product_weight_g IS NOT NULL
    AND promised_days IS NOT NULL AND purchase_dow IS NOT NULL
    AND purchase_month IS NOT NULL
    AND payment_type IS NOT NULL AND customer_state IS NOT NULL
    AND seller_state IS NOT NULL AND product_category_name IS NOT NULL));

-- 5. Agent audit explorer: created after scripts/e2e_agent_cloud.py runs,
-- because the agent_audit table is created by that script.
-- CREATE OR REPLACE VIEW `delivery-experience-511901.dei_mart.v_agent_audit` AS
-- SELECT * FROM `delivery-experience-511901.dei_mart.agent_audit`
-- ORDER BY decided_at DESC;
