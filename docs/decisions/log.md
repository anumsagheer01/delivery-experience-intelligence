# Decision log

## D1. Four datasets, kept independent
Olist (orders), Amazon Last-Mile (routes), OpenStreetMap (places), Open Images
(photos) come from different companies, countries, and years. Joining them as
if they described the same deliveries would be fabrication. Each module is
evaluated on its natural dataset; cross-module behavior uses clearly labeled
controlled scenarios.

## D2. ELT over ETL
Raw files land untouched in storage; all transformation happens in SQL/Python
against copies. Rationale: auditability and reproducibility. Cost: storage is
cheap; the discipline is worth it.

## D3. Replay instead of simulation
The streaming demo replays real Olist timestamps through Pub/Sub. This is the
industry backfill pattern and keeps the "real data only" rule intact.

## D4. BigQuery as the analytical store, DuckDB for local execution
BigQuery is the production target (serverless, GIS, ML in SQL). This build
environment has no GCP credentials, so all SQL is also validated locally with
DuckDB where the dialect overlaps. Anything not executed in GCP is labeled
as such in STATUS.md.

## D5. Baselines first
OpenCV blur/brightness before AutoML/Gemini; logistic regression and dummy
classifiers before gradient boosting. A baseline that wins is a finding.

## D6. Temporal splits for risk models
Train before 2018-01-01, test after. Random splits leak future information in
time-ordered data. Purchase-time features only; actual delivery timestamps are
never features.

## D7. Leakage-controlled address labels
Labels from commercial-activity tags; features exclude those tags. Same-tag
features would let the model memorize the labeling rule.

## D8. Vision cascade
Binary package-visible classifier (cheap, high volume) -> Gemini SOP judgment
(expensive, nuanced). Each layer does what it is cheapest at.

## D9. Drafts-only agent
The agent never sends customer/driver communications. v1 output is a draft
queue for human approval. Escalation threshold 0.6 is provisional and must be
validated, not treated as universal.

## D10. No purpose-collected POD photos
Photographing real doorsteps is a privacy minefield. We use Open Images with
disclosed weak supervision plus a human-reviewed benchmark, and never present
automatic labels as human ground truth.
