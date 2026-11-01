-- Driver Intelligence schema: PRODUCTION PATH ONLY (BigQuery DDL).
-- This file is not executed by the local demo. The demo uses the
-- SQLite store in src/driver_intelligence/memory.py, which implements
-- the same fields, at zero cloud cost. To use this DDL, replace PROJECT
-- and run it in BigQuery with valid GCP credentials.
-- Synthetic demo data must never be loaded into these tables as if
-- it were real customer data.
--
-- Tables: driver_assignments (authorization), stop_profiles (current
-- memory), stop_observations (append-only history), driver_feedback.

CREATE SCHEMA IF NOT EXISTS `PROJECT.driver_intelligence`;

CREATE TABLE IF NOT EXISTS `PROJECT.driver_intelligence.driver_assignments` (
  driver_id STRING NOT NULL,
  stop_id STRING NOT NULL,
  assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (driver_id, stop_id) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS `PROJECT.driver_intelligence.stop_profiles` (
  stop_id STRING NOT NULL,
  address_id STRING,
  building_type STRING,
  preferred_entrance STRING,
  preferred_placement STRING,
  contact_preference STRING,
  access_instructions STRING,
  -- Reference only. Never store a gate code value in this column.
  gate_code_ref STRING,
  gate_verification_status STRING,
  leave_unattended_restriction BOOL,
  leave_restriction_reason STRING,
  known_access_problems STRING,
  instruction_source STRING,
  verification_status STRING,
  confidence FLOAT64,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  expires_at TIMESTAMP,
  is_current BOOL
);

CREATE TABLE IF NOT EXISTS `PROJECT.driver_intelligence.stop_observations` (
  observation_id INT64 NOT NULL,
  stop_id STRING NOT NULL,
  kind STRING,
  text STRING,
  source_type STRING,
  verification_status STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  is_restriction BOOL
);

CREATE TABLE IF NOT EXISTS `PROJECT.driver_intelligence.driver_feedback` (
  feedback_id INT64 NOT NULL,
  driver_id STRING,
  stop_id STRING,
  feedback_type STRING,
  note STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  applied STRING
);
