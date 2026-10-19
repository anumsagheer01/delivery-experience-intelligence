-- BigQuery ML: late-delivery risk (mirrors src/ml trained locally with sklearn).
-- Temporal split: train < 2018-01-01, evaluate after. Purchase-time features only.
-- Replace PROJECT. Execution needs GCP credentials; local equivalent in src/ml/.

CREATE OR REPLACE MODEL `PROJECT.delivery_marts.late_delivery_risk`
OPTIONS(model_type='BOOSTED_TREE_CLASSIFIER',
        input_label_cols=['is_late'], max_tree_depth=6, learn_rate=0.1) AS
WITH base AS (
  SELECT
    o.order_id, o.order_purchase_timestamp,
    CASE WHEN DATE(o.order_delivered_customer_date) > DATE(o.order_estimated_delivery_date)
         THEN 1 ELSE 0 END AS is_late,
    pay.payment_type, pay.payment_installments,
    it.price, it.freight_value,
    c.customer_state, s.seller_state,
    p.product_category_name,
    DATE_DIFF(DATE(o.order_estimated_delivery_date),
              DATE(o.order_purchase_timestamp), DAY) AS promised_days
  FROM `PROJECT.delivery_raw.olist_orders` o
  JOIN `PROJECT.delivery_raw.olist_order_items` it USING (order_id)
  JOIN `PROJECT.delivery_raw.olist_order_payments` pay USING (order_id)
  JOIN `PROJECT.delivery_raw.olist_customers` c USING (customer_id)
  JOIN `PROJECT.delivery_raw.olist_sellers` s USING (seller_id)
  JOIN `PROJECT.delivery_raw.olist_products` p USING (product_id)
  WHERE o.order_status = 'delivered'
    AND o.order_delivered_customer_date IS NOT NULL
    AND o.order_purchase_timestamp < '2018-01-01')
SELECT * EXCEPT (order_id, order_purchase_timestamp) FROM base;

-- evaluate on the future holdout + ROC curve for threshold analysis
SELECT * FROM ML.EVALUATE(
  MODEL `PROJECT.delivery_marts.late_delivery_risk`,
  (SELECT * EXCEPT (order_id) FROM (
    SELECT o.order_id, o.order_purchase_timestamp,
      CASE WHEN DATE(o.order_delivered_customer_date) > DATE(o.order_estimated_delivery_date)
           THEN 1 ELSE 0 END AS is_late, pay.payment_type, pay.payment_installments,
      it.price, it.freight_value, c.customer_state, s.seller_state,
      p.product_category_name,
      DATE_DIFF(DATE(o.order_estimated_delivery_date),
                DATE(o.order_purchase_timestamp), DAY) AS promised_days
    FROM `PROJECT.delivery_raw.olist_orders` o
    JOIN `PROJECT.delivery_raw.olist_order_items` it USING (order_id)
    JOIN `PROJECT.delivery_raw.olist_order_payments` pay USING (order_id)
    JOIN `PROJECT.delivery_raw.olist_customers` c USING (customer_id)
    JOIN `PROJECT.delivery_raw.olist_sellers` s USING (seller_id)
    JOIN `PROJECT.delivery_raw.olist_products` p USING (product_id)
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
      AND o.order_purchase_timestamp >= '2018-01-01')));

-- business-vs-residential address classifier on OSM public data.
-- Leakage control: label from commercial-activity tags; features exclude them.
CREATE OR REPLACE MODEL `PROJECT.delivery_marts.address_classifier`
OPTIONS(model_type='LOGISTIC_REG', input_label_cols=['is_business']) AS
WITH raw AS (
  SELECT
    osm_id, ST_CENTROID(geometry) AS geo, ST_AREA(geometry) AS geom_area,
    ARRAY_LENGTH(all_tags) AS num_tags,
    (SELECT COUNT(*) FROM UNNEST(all_tags) t
       WHERE t.key IN ('shop','amenity','office','craft')) AS commercial_tags,
    (SELECT MAX(t.value) FROM UNNEST(all_tags) t WHERE t.key='building') AS building_value,
    (SELECT MAX(CASE WHEN t.key='addr:housenumber' THEN 1 ELSE 0 END)
       FROM UNNEST(all_tags) t) AS has_housenumber,
    (SELECT MAX(CASE WHEN t.key='name' THEN 1 ELSE 0 END)
       FROM UNNEST(all_tags) t) AS has_name
  FROM `bigquery-public-data.geo_openstreetmap.planet_features`
  TABLESAMPLE SYSTEM (0.5 PERCENT)
  WHERE geometry IS NOT NULL
    AND ST_Y(ST_CENTROID(geometry)) BETWEEN -34 AND 6
    AND ST_X(ST_CENTROID(geometry)) BETWEEN -74 AND -34)
SELECT
  CASE WHEN commercial_tags > 0 THEN 1 ELSE 0 END AS is_business,
  geom_area, num_tags, has_housenumber, has_name,
  ST_X(geo) AS lon, ST_Y(geo) AS lat
FROM raw
WHERE commercial_tags > 0
   OR building_value IN ('house','residential','apartments','detached','terrace');
