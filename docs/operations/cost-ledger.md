# Cost ledger

All figures in USD. 

## Projected GCP costs 

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
