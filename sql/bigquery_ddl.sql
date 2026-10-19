-- BigQuery DDL: raw/staging/mart layers for the delivery platform.
-- Replace PROJECT with your GCP project id. Run in dependency order.
-- These were developed against the real schemas; execution needs GCP credentials.

-- ============ raw layer (untouched source of truth) ============
CREATE SCHEMA IF NOT EXISTS `PROJECT.delivery_raw`;

-- Olist raw tables loaded from CSV (bq load --autodetect --skip_leading_rows=1):
-- delivery_raw.olist_orders, olist_customers, olist_order_items,
-- olist_order_payments, olist_order_reviews, olist_sellers, olist_products,
-- olist_geolocation

-- Amazon raw tables loaded from normalized JSONL:
CREATE TABLE IF NOT EXISTS `PROJECT.delivery_raw.amazon_stops` (
  route_id STRING, stop_id STRING, lat FLOAT64, lng FLOAT64,
  zone_id STRING, stop_type STRING, planned_service_time_s INT64
);
CREATE TABLE IF NOT EXISTS `PROJECT.delivery_raw.amazon_sequences` (
  route_id STRING, actual_sequence ARRAY<STRING>
);

-- streaming events (written by the Pub/Sub BigQuery subscription):
CREATE TABLE IF NOT EXISTS `PROJECT.delivery_raw.delivery_events` (
  event_id STRING, order_id STRING, event_type STRING,
  event_time TIMESTAMP, processed_time TIMESTAMP, order_status STRING
);

-- vision + agent outputs:
CREATE TABLE IF NOT EXISTS `PROJECT.delivery_raw.pod_scores` (
  order_id STRING, gcs_uri STRING, quality STRING,
  package_visible BOOL, confidence FLOAT64,
  scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
CREATE TABLE IF NOT EXISTS `PROJECT.delivery_raw.interventions` (
  event_id STRING, order_id STRING, event_type STRING, action STRING,
  confidence FLOAT64, rationale STRING, draft STRING,
  decided_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- ============ marts (analytics-ready views) ============
CREATE SCHEMA IF NOT EXISTS `PROJECT.delivery_marts`;

CREATE OR REPLACE VIEW `PROJECT.delivery_marts.v_event_funnel` AS
SELECT event_type, COUNT(*) AS events, COUNT(DISTINCT order_id) AS orders
FROM `PROJECT.delivery_raw.delivery_events`
GROUP BY event_type;

CREATE OR REPLACE VIEW `PROJECT.delivery_marts.v_late_vs_reviews` AS
WITH d AS (
  SELECT o.order_id,
    DATE(o.order_delivered_customer_date) > DATE(o.order_estimated_delivery_date) AS is_late,
    r.review_score
  FROM `PROJECT.delivery_raw.olist_orders` o
  JOIN `PROJECT.delivery_raw.olist_order_reviews` r USING (order_id)
  WHERE o.order_status = 'delivered')
SELECT is_late, COUNT(*) AS orders, ROUND(AVG(review_score), 2) AS avg_review
FROM d GROUP BY is_late;

CREATE OR REPLACE VIEW `PROJECT.delivery_marts.v_pod_quality_daily` AS
SELECT DATE(scored_at) AS day, COUNT(*) AS photos,
  ROUND(100 * AVG(CASE WHEN quality IN
    ('no_package','wrong_location','unsafe_placement') THEN 1.0 ELSE 0 END), 1)
    AS bad_photo_pct
FROM `PROJECT.delivery_raw.pod_scores`
GROUP BY day ORDER BY day;

CREATE OR REPLACE VIEW `PROJECT.delivery_marts.v_agent_actions` AS
SELECT action, COUNT(*) AS n, ROUND(AVG(confidence), 2) AS avg_confidence
FROM `PROJECT.delivery_raw.interventions`
GROUP BY action ORDER BY n DESC;
