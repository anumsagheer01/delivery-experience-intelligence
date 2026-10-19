-- Experiment exposure logging for the outreach A/B test.
-- One row per customer the first time they trigger (have a flagged order).
-- Assignment itself is deterministic (hash of customer id), so this table
-- is the analysis record, not the source of truth for arms.
-- Run in Cloud Shell: bq query --use_legacy_sql=false < sql/experiment_exposures.sql

CREATE TABLE IF NOT EXISTS `delivery-experience-511901.dei_mart.experiment_exposures`
(
  experiment_id STRING NOT NULL,
  customer_unique_id STRING NOT NULL,
  arm STRING NOT NULL,               -- 'control' or 'treatment'
  assigned_at TIMESTAMP NOT NULL,    -- first trigger time (UTC)
  triggered_order_id STRING NOT NULL,
  trigger_reason STRING,             -- why the agent flagged this order
  risk_score FLOAT64,                -- BQML late-delivery risk at trigger
  review_score INT64,                -- filled when the review arrives (NULL until then)
  message_drafted BOOL NOT NULL,     -- TRUE only for treatment arm
  message_sent BOOL NOT NULL,        -- always FALSE: dry-run only, no sends
  covariate_order_value FLOAT64,     -- pre-treatment, for CUPED screening
  covariate_freight_value FLOAT64
)
PARTITION BY DATE(assigned_at)
OPTIONS (
  description = 'Outreach experiment exposures. Dry-run only: message_sent is always FALSE.'
);
