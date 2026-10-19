# Cloud Operations Scripts

These scripts ran in Google Cloud Shell (project
`delivery-experience-511901`) against real GCP services. They are kept
here so the cloud half of the project is reviewable and reproducible
by anyone with access to the project. Nothing here runs locally without
GCP credentials; the local test suite does not depend on them.

## What each script does

| Script | Purpose |
| --- | --- |
| `verify_agent_audit.py` | Independently recomputes all 500 cloud agent decisions from warehouse facts plus BQML scores (fresh implementation of the policy, not the agent's code) and asserts every recorded action matches. Result: 500/500 match. See `evals/agent/verify_audit_500.json`. |
| `gemini_eval.py` | Runs the structured SOP photo evaluation over the 114-image set via Vertex AI (Gemini 2.5 Flash; 2.0 Flash was retired). Summary: `evals/vision/gemini_eval_summary.json`. |
| `fetch_s3.py` | Downloads the 4,712 dataset images from the official Open Images S3 mirror directly into the GCS bucket, verifying per-file SHA256 against `data/vision/manifest.csv`. |
| `verify_upload_flickr85.py` | Verifies the 85 full-resolution Flickr originals landed in GCS with correct hashes. |
| `stage3.sh` | Creates the Vertex AI image dataset, imports the CSV manifest, and launches the AutoML training pipeline via the Vertex AI REST API (the fixed revision; `inputDataConfig.datasetId` is the correct field). |
| `experiment_exposures.sql` | DDL for the `dei_mart.experiment_exposures` BigQuery table used by the A/B testing module. |
| `publish_events.py` | Publishes the 19,770 real Olist order lifecycle events to the `dei-order-events` Pub/Sub topic. |
| `verify_pubsub.py` | Verifies Pub/Sub throughput and zero message loss. |
| `convert_amazon.py` | Converts the raw Amazon Last-Mile Routing data into BigQuery-loadable tables. |

## Requirements

- Google Cloud SDK (`gcloud`, `gsutil`, `bq`) authenticated to the project
- Python 3.10+ with `google-cloud-bigquery`, `google-cloud-pubsub`, `google-cloud-aiplatform`
- The GCS bucket and BigQuery dataset created first (see `docs/operations/gcp-setup.md`)

Build artifacts (image tarballs, download logs, batch prediction
outputs) are not committed; the canonical copies live in GCS at
`gs://dei-raw-67129202721/`.
