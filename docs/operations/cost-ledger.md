# Cost ledger

All figures in USD. "Measured" means observed in this environment or quoted
from official pricing at build time. Nothing here was charged to the GCP
project, because this environment has no GCP credentials (see STATUS.md).

## Local execution (this build): $0

Everything executed here ran on a local VM: dataset downloads (public
registries), DuckDB, scikit-learn, OpenCV. No cloud spend.

## Projected GCP costs for the documented deployment

| Component | Basis | Projected cost |
|---|---|---|
| BigQuery storage (Olist ~150 MB + events) | $0.02/GB/month | < $0.10/month |
| BigQuery queries (within 1 TB free tier) | first 1 TB/month free | $0 |
| OSM planet query (TABLESAMPLE 0.5%) | bytes-billed cap enforced | < $1 per run |
| Pub/Sub replay (~400k messages) | first 10 GB free | $0 |
| Cloud Run (min instances 0) | per-request | < $1 for demo |
| Vertex AI AutoML image training | ~3 node-hours (estimate; verify in console) | $10-$60 one-time |
| Gemini flash eval (300 images) | per-1k images pricing | < $2 |
| Cloud Vision (300 images) | first 1000/month free | $0 |

Total projected deployment: well under the $50 target excluding AutoML
training, which is the one line item to verify in the console before running.
The enforced caps ($10 Gemini, $10 Vertex AI, $5 Cloud Run monthly) bound the
worst case even if estimates are off.

## Rules applied

- Budgets are alerts, not limits. Enforced caps are set separately.
- BigQuery maximum bytes billed is set on every analytical query.
- No Dataflow streaming jobs (would idle-burn); the documented Dataflow
  comparison is batch or short-lived only.
- Vertex AI endpoints are deleted after evaluation; artifacts kept in GCS.
- Cloud Run minimum instances = 0 everywhere.
