# STATUS: what is real, what is not

Updated 2026-10-18 (AutoML trained, evaluated, integrated). Every claim below is verifiable in this repo or in GCP project delivery-experience-511901.

## Completed and tested (local)

- Repo scaffold with configs, logging, manifests, .gitignore, secret hygiene
- 31 unit tests passing (`pytest tests/`)
- Olist ingestion: 9 CSVs downloaded from the official Olist GitHub mirror,
  schema validation clean, data-quality report measured
  (99,441 orders, 96,478 delivered, 8.11% late)
- Risk models (sklearn): logistic regression, dummy, and gradient boosting
  trained on real Olist data with temporal splits; metrics in `evals/risk/`
  (is_late HGB ROC-AUC 0.649; is_low_review HGB ROC-AUC 0.601)
- Amazon Last-Mile: 6,112 routes / 904,527 stops parsed; zone fragmentation
  measured (64.4% of routes re-enter a zone; 2.62 revisits/route)
- Vision baselines: OpenCV blur/brightness measured on 114 real Open Images
  photos (`evals/vision/opencv_baselines.csv`)
- Agent policy + dry-run evaluation: 5/5 controlled scenarios match
- Agent end-to-end loop on real data: 1,946 DELIVERED orders, 78/78
  late+low-review orders correctly triggered draft_customer_message
  (`evals/agent/e2e_local_results.json`, scripts/e2e_local.py)
- Dashboard preview charts rendered from real data (`dashboard/preview/`)

## Completed and tested (GCP, project delivery-experience-511901)

Executed 2026-10-17 via Cloud Shell (user authorized in person).
APIs enabled: bigquery, pubsub, storage, aiplatform.

- GCS bucket `gs://dei-raw-67129202721/` with 12 raw files (562 MB)
- BigQuery dataset `dei_mart` (us-central1), 13 tables, row counts verified:
  orders 99,441; order_items 112,650; order_payments 103,886;
  order_reviews 99,224; customers 99,441; sellers 3,095; products 32,951;
  geolocation 1,000,163; category_translation 71; amz_routes 6,112;
  amz_stops 904,527; amz_packages 904,527; amz_sequences 6,112
- BigQuery ML `late_delivery_risk` (boosted trees, temporal split):
  holdout ROC-AUC 0.6156, log-loss 0.3074 (`evals/risk/bqml/`)
- BigQuery ML `low_review_risk`: holdout ROC-AUC 0.5751, log-loss 0.3904
- Pub/Sub topic `dei-order-events` + subscription: 19,770 real events
  published in 3.2 s = 6,235 events/s measured cloud throughput,
  zero loss, schema verified (`evals/streaming/pubsub_cloud.json`)
- Dashboard: 4 BigQuery views LIVE in `dei_mart`
  (`sql/dashboard_views.sql`): v_late_by_state, v_late_vs_reviews,
  v_zone_revisits, v_risk_scores

## Partially completed

- Open Images download: 114 of ~260 target images fetched (Flickr rate limits);
  downloader script is resumable
- OSM Austin parse: 80,000 elements parsed locally; BigQuery GIS path written

## Completed and tested (GCP, project delivery-experience-511901): AutoML vision track, 2026-10-18

- POD dataset: 4,712 real Open Images photos verified in GCS
  (`gs://dei-raw-67129202721/raw/vision/pod_dataset/`), per-file SHA256
  checked against `data/vision/manifest.csv`. Composition: 4,627 S3-mirror 1024px
  + 85 Flickr full-resolution originals (same photos/annotations; the S3
  downloader had skipped them as already-present). 2,212 package_present
  (human Box annotations) / 2,500 door_no_package. Splits (seed 17):
  TRAIN 3770 / VALIDATION 471 / TEST 471, cluster-aware, zero TEST/eval
  overlap. Manual audit passed (250 images). Provenance:
  `data/vision/manifest_provenance.json`.
- Vertex AI dataset 263421270660481024 (`dei-pod-photos-v1`), CSV import
  of `automl_import.csv` completed.
- AutoML training pipeline `dei-pod-automl-v1` COMPLETE (state DONE):
  projects/67129202721/locations/us-central1/trainingPipelines/7675807299046211584.
  CLOUD model type, 8,000 milli node-hours (~$27.72 gross, under the $35
  approved ceiling). Model:
  projects/67129202721/locations/us-central1/models/2263085750788554752.
  No endpoint deployed (batch prediction only, by design). No duplicates.
- Vertex eval: auPrc 0.9937; at confidence 0.6, recall 0.9618,
  precision 0.9869 (`evals/vision/automl_test_metrics.json`).
- Held-out TEST via batch prediction job `dei-pod-automl-batch-test`
  (471/471 matched, 0 unmatched): accuracy 0.9958; door_no_package
  P 0.9921 / R 1.0000 / F1 0.9960; package_present P 1.0000 / R 0.9910 /
  F1 0.9955; confusion [[250,0],[2,219]]. Outputs archived in GCS
  (`.../pod_dataset/batch_eval/`).
- Cost safeguards honored: Vertex AI cap was temporarily $50 for
  training (user-approved) and was restored to $10 immediately after
  evaluation completed (2026-10-18). Total project spend within the $50
  hard cap; trial credits cover usage.
- Integration: `src/vision/automl.py` (model client, batch workflow,
  scoring, PodAssessor for the agent); `src/agents/cloud_context.py`
  gained `attach_pod_quality()`; 4 new unit tests, 31 total passing.
  Decision doc: `docs/decisions/vision_model.md`.
- Gemini SOP evaluation COMPLETE (2026-10-18): 113/114 validation
  photos scored via Vertex AI. Honest deviation: gemini-2.0-flash
  returned 404 (retired), so gemini-2.5-flash was substituted after a
  verified test call. Against weak labels: 64.6% agreement (48 tp,
  0 fp, 25 tn, 40 fn), conservative with zero false alarms; OpenCV
  heuristic 70.2% on the same weak labels. These measure agreement
  with a noisy proxy, not accuracy, and are not ranked against the
  AutoML 99.6% clean-test result. Summary:
  `evals/vision/gemini_eval_summary.json`; full rows in GCS.

## Not completed (honestly labeled)

- Cloud Run deployment (Dockerfile + service code ready)
- Human review of the 300-image benchmark via the labeling app
- Looker Studio connection (manual step; BigQuery views are live)

## Proposed future work

- Human review of the 300-image benchmark via the labeling app
- Dataflow streaming comparison, model monitoring, online feature store
- See `docs/decisions/future-work.md`

## What was NOT done and is NOT claimed

- No metrics were invented. Every number traces to a script and a data file.
- No cross-dataset joins are presented as real observations.
- No customer or driver messages were sent (drafts only, dry-run).
- GCP spend: Vertex AI training cost ~$27.72 gross, covered by the $300
  trial credits ($0 out of pocket); enforced budget caps respected
  throughout, Vertex AI cap restored to $10 after evaluation.
