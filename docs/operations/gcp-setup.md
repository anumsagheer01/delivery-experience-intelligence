# GCP setup and teardown

## Prerequisites (manual, needs the project owner)

1. `gcloud auth login` and `gcloud config set project delivery-experience-511901`
2. Verify billing account and budgets in the console: Billing -> Budgets.
   Confirm the $50 alert budget and the enforced caps ($10 Gemini, $10 Vertex
   AI, $5 Cloud Run monthly) BEFORE running anything billable.
3. Enable APIs: BigQuery, Cloud Storage, Pub/Sub, Vertex AI, Cloud Run,
   Cloud Vision, Generative Language (Gemini).

## Deploy order

```bash
# storage + datasets
gsutil mb -l us-central1 gs://delivery-experience-511901-raw
bq mk --dataset --location=US delivery-experience-511901:delivery

# schema
bq query --use_legacy_sql=false < sql/bigquery_ddl.sql

# pub/sub topology
gcloud pubsub topics create order-events
gcloud pubsub subscriptions create order-events-bq \
  --topic=order-events \
  --bigquery-table=delivery-experience-511901:delivery.delivery_events \
  --use-table-schema

# replay
python -m src.streaming --mode pubsub --project delivery-experience-511901

# train risk models in BigQuery ML
bq query --use_legacy_sql=false < sql/bigquery_ml.sql
```

## Teardown (run after experiments)

```bash
# delete endpoints first (the expensive idle resource)
gcloud ai endpoints list --region=us-central1   # delete any created
# stop to zero
gcloud run services update --min-instances=0 --region=us-central1 $(gcloud run services list --format='value(name)')
# optionally delete the dataset (keeps the project; data re-downloadable)
bq rm -r -f delivery-experience-511901:delivery
```

Data is never the thing you protect here; code and manifests are. Raw data
re-downloads from public sources in minutes.
