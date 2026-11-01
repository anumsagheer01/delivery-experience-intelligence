# Model Card: dei-pod-automl-v1

## Model details
- **Name:** dei-pod-automl-v1 (Vertex AI AutoML image classification)
- **Model ID:** projects/67129202721/locations/us-central1/models/2263085750788554752
- **Training pipeline:** projects/67129202721/locations/us-central1/trainingPipelines/7675807299046211584 (state: DONE)
- **Dataset:** 263421270660481024 (dei-pod-photos-v1)
- **Trained:** 2026-10-18. **Framework:** Vertex AI AutoML (CLOUD model type).
- **Training config:** modelType CLOUD, budget 8,000 milli node-hours, multiLabel false.
- **Training cost:** ~$27.72 gross (under the approved $35 ceiling; $300 promotional credits applied, $0 out of pocket).

## Intended use
Binary proof-of-delivery photo classification: does the photo show a
delivered package (package_present) or a door with no package visible
(door_no_package)? Designed as the middle layer of a cost-ordered
cascade: OpenCV blur/brightness checks first (free), this classifier
second (cheap, high volume via batch prediction), Gemini structured
SOP judgment third (expensive, ambiguous cases only). Consumed by the
intervention agent via src/vision/automl.py PodAssessor; no online
endpoint is deployed (batch prediction only, by design).

## Training data
- **4,712 real Open Images photos**, verified per-file SHA256 against
  oid/manifest.csv before GCS upload.
- **Positives (2,212):** images with human-drawn Box annotations
  (/m/025dyy) from Open Images 2018_04 train.
- **Negatives (2,500):** images with human-drawn Door annotations
  (/m/02dgv) and no Box annotation, sampled.
- **Source mix (documented):** 4,627 from the official Open Images CVDF
  S3 mirror (1024px) + 85 Flickr full-resolution originals (same photos
  and annotations; the S3 downloader had skipped them as already-present).
  See oid/manifest_provenance.json.
- **Splits (seed 17, cluster-aware, per-class):** TRAIN 3770 (2000 door /
  1770 package), VALIDATION 471, TEST 471. Zero exact duplicates; 7
  near-duplicate dHash clusters, all confined to single splits. Zero
  overlap with the 114-image eval set.
- **Audit:** 250-image manual review passed (149/150 negatives clean,
  0 clear packages; 100/100 positives consistent with annotations).

## Evaluation
- **Vertex AI eval:** auPrc 0.9937; at confidence 0.6, recall 0.9618, precision 0.9869.
- **Held-out TEST (n=471) via batch prediction** (job dei-pod-automl-batch-test,
  471/471 predictions matched, 0 unmatched):
  - Accuracy: 0.9958
  - door_no_package (n=250): precision 0.9921, recall 1.0000, F1 0.9960
  - package_present (n=221): precision 1.0000, recall 0.9910, F1 0.9955
  - Confusion (rows actual, cols predicted): [[250, 0], [2, 219]]
- Evidence: evals/vision/automl_test_metrics.json; batch outputs in
  GCS gs://dei-raw-67129202721/raw/vision/pod_dataset/batch_eval/.

## Limitations
- Binary task only (package visible: yes/no); it does not assess photo
  quality dimensions (blur, lighting, placement). Those are the
  OpenCV baseline and Gemini SOP layers of the cascade.
- Training labels derive from Open Images bounding-box annotations
  (human-drawn, high quality) but were not re-verified per image beyond
  the 250-image audit sample.
- The 85 full-resolution images differ in resolution from the rest;
  AutoML resizes inputs internally. Per-image error analysis (which
  specific test images were misclassified) was not run; the aggregate
  metrics above are the complete measured claim.
- Intended for batch scoring, not real-time single-image serving.

## Ethical considerations
- No people are identified; photos are of doors and packages from a
  public research dataset (Open Images, CC-BY annotations).
- The agent that consumes these scores runs in dry-run only; no
  customer or driver is contacted automatically.
- Dataset licensing: image licenses recorded per image in
  oid/download_list.json; comply with CC-BY attribution where required.
