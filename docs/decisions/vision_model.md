# Vision model: training, evaluation, and agent integration

Date: 2026-10-18. Status: TRAINED, EVALUATED, INTEGRATED.

## What was built

AutoML image classifier `dei-pod-automl-v1` (Vertex AI, CLOUD model type,
8 node-hours, ~$27.72 gross, under the approved $35 ceiling). Training
data: 4,712 real Open Images photos (2,212 package_present from human Box
annotations, 2,500 door_no_package), cluster-aware splits (seed 17):
TRAIN 3770 / VALIDATION 471 / TEST 471. Zero overlap between TEST and the
114-image eval set; dedupe verified (0 exact dupes; 7 near-duplicate
clusters confined to single splits).

## Measured results (not estimates)

- Vertex eval: auPrc 0.9937; at confidence 0.6, recall 0.9618, precision 0.9869.
- Held-out TEST via batch prediction (471/471 matched): accuracy 0.9958.
  door_no_package: P 0.9921, R 1.0000, F1 0.9960. package_present:
  P 1.0000, R 0.9910, F1 0.9955. Confusion [[250,0],[2,219]].
- Evidence: evals/vision/automl_test_metrics.json; batch outputs archived
  in GCS under gs://dei-raw-67129202721/raw/vision/pod_dataset/batch_eval/.

## Key decisions

1. Batch prediction, not an online endpoint. An endpoint costs $1.375/hr
   to sit idle; batch is $2.222/node-hour pay-per-use. POD photos arrive
   in daily batches in this design, so batch fits the workload and the
   budget. The agent consumes pre-computed batch results
   (src/vision/automl.py: PodAssessor); a photo with no batch result is
   reported as unknown, never as a negative.
2. Kept the 85 Flickr full-resolution originals instead of replacing them
   with S3 1024px versions. They are the same photos and annotations;
   replacing them would have invalidated the dedupe analysis done on the
   exact bytes. Dual provenance is documented in
   data/vision/manifest_provenance.json.
3. Fair comparison discipline: AutoML is compared against the OpenCV
   baselines on the same binary task (package_visible). Gemini's
   structured SOP verdict is a richer task and is reported separately,
   not as a single-number ranking (see evals/vision/).

## Agent integration

src/agents/cloud_context.py builds order context from BigQuery
(risk_score from the BQML late_delivery_risk model). The pod_quality
field is filled by the vision path: batch-predict the day's POD photos,
load results into PodAssessor, and attach assess(gcs_uri) per order.
The intervention policy (src/agents/__init__.py) is unchanged: dry-run
only, nothing is ever sent.
