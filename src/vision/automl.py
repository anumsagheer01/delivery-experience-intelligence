"""Trained AutoML vision model: client, batch workflow, and scoring.

Model: dei-pod-automl-v1 (Vertex AI AutoML image classification, CLOUD)
  training pipeline: projects/67129202721/locations/us-central1/trainingPipelines/7675807299046211584
  model:             projects/67129202721/locations/us-central1/models/2263085750788554752
  dataset:           263421270660481024 (4,712 images, cluster-aware splits,
                     seed 17; TRAIN 3770 / VALIDATION 471 / TEST 471)
  training config:   modelType CLOUD, budget 8000 milli node-hours
  training data:     4,627 Open Images S3 mirror 1024px photos + 85 Flickr
                     full-resolution originals (same photos/annotations;
                     see data/vision/manifest_provenance.json)

Measured performance (never fabricate; see evals/vision/):
  Vertex eval:       auPrc 0.9937; at conf 0.6, recall 0.9618, precision 0.9869
  Held-out TEST:     accuracy 0.9958 (469/471); door_no_package F1 0.9960;
                     package_present F1 0.9955; confusion [[250,0],[2,219]]

Design decision: NO online endpoint is deployed (an endpoint costs
$1.375/hr to sit idle). The production path is batch prediction
($2.222/node-hour, pay per use). assess_pod_photo() therefore works from
batch prediction results, not a live call. This is documented, not hidden.
"""
import csv
import json
import os

PROJECT = "delivery-experience-511901"
LOCATION = "us-central1"
PROJECT_NUMBER = "67129202721"

TRAINING_PIPELINE = (
    f"projects/{PROJECT_NUMBER}/locations/{LOCATION}"
    "/trainingPipelines/7675807299046211584"
)
MODEL_ID = (
    f"projects/{PROJECT_NUMBER}/locations/{LOCATION}"
    "/models/2263085750788554752"
)
DATASET_ID = "263421270660481024"
GCS_PREFIX = "gs://dei-raw-67129202721/raw/vision/pod_dataset"

CLASSES = ["door_no_package", "package_present"]

# Measured on the 471-image held-out TEST split via batch prediction
# (job dei-pod-automl-batch-test, 2026-10-18). Do not edit by hand;
# regenerate with score_predictions().
TEST_METRICS = {
    "accuracy": 0.9958,
    "n": 471,
    "door_no_package": {"precision": 0.9921, "recall": 1.0,
                        "f1": 0.9960, "support": 250},
    "package_present": {"precision": 1.0, "recall": 0.9910,
                        "f1": 0.9955, "support": 221},
    "confusion": [[250, 0], [2, 219]],
}


def parse_prediction_line(line: str) -> dict:
    """Parse one AutoML batch-prediction JSONL line.

    Returns {"gcs_uri", "predicted_label", "confidence"}. Raises
    ValueError on malformed lines (never silently mislabels).
    """
    obj = json.loads(line)
    uri = obj.get("content")
    pred = obj.get("prediction", {})
    names = pred.get("displayNames") or pred.get("display_names") or []
    scores = pred.get("confidences") or pred.get("scores") or []
    if not uri or not names or not scores or len(names) != len(scores):
        raise ValueError(f"malformed prediction line: {line[:200]}")
    best = max(range(len(scores)), key=lambda i: scores[i])
    return {"gcs_uri": uri, "predicted_label": names[best],
            "confidence": float(scores[best])}


def score_predictions(pred_lines: list, manifest_path: str) -> dict:
    """Score batch predictions against manifest ground truth.

    pred_lines: iterable of raw JSONL strings. manifest_path: manifest.csv
    (CRLF endings, header row; columns image_id,label,ml_use,gcs_uri,
    local_file,sha256). Only TEST rows are scored. Returns the metrics
    dict (same shape as TEST_METRICS).
    """
    truth = {}
    with open(manifest_path, newline="") as f:
        for row in csv.DictReader(f):
            if row["ml_use"] == "TEST":
                truth[row["gcs_uri"].strip()] = row["label"].strip()
    labels = CLASSES
    cm = [[0, 0], [0, 0]]
    matched = unmatched = 0
    for line in pred_lines:
        if not line.strip():
            continue
        p = parse_prediction_line(line)
        actual = truth.get(p["gcs_uri"])
        if actual is None:
            unmatched += 1
            continue
        matched += 1
        cm[labels.index(actual)][labels.index(p["predicted_label"])] += 1

    def prf(tp, fp, fn):
        prec = tp / max(tp + fp, 1)
        rec = tp / max(tp + fn, 1)
        f1 = 2 * prec * rec / max(prec + rec, 1e-9)
        return round(prec, 4), round(rec, 4), round(f1, 4)

    out = {"n": matched, "unmatched": unmatched, "confusion": cm}
    for i, cls in enumerate(labels):
        tp = cm[i][i]
        fp = sum(cm[r][i] for r in range(2)) - tp
        fn = sum(cm[i]) - tp
        prec, rec, f1 = prf(tp, fp, fn)
        out[cls] = {"precision": prec, "recall": rec, "f1": f1,
                    "support": sum(cm[i])}
    out["accuracy"] = round(sum(cm[i][i] for i in range(2)) / max(matched, 1), 4)
    return out


class PodAssessor:
    """Agent-facing POD photo assessment backed by batch predictions.

    Usage: run batch prediction over the day's POD photos, load the
    results JSONL once, then call assess() per order. No endpoint, no
    per-call cost, no credentials needed at call time.
    """

    def __init__(self, predictions_path: str):
        self._by_uri = {}
        with open(predictions_path) as f:
            for line in f:
                if line.strip():
                    p = parse_prediction_line(line)
                    self._by_uri[p["gcs_uri"]] = p

    def assess(self, gcs_uri: str) -> dict:
        """Return {"package_visible", "confidence", "assessed"}.

        assessed=False (with package_visible=None) when no batch
        prediction exists for this URI: the agent must treat that as
        unknown, never as a negative.
        """
        p = self._by_uri.get(gcs_uri)
        if p is None:
            return {"package_visible": None, "confidence": None,
                    "assessed": False}
        return {"package_visible": p["predicted_label"] == "package_present",
                "confidence": p["confidence"], "assessed": True}
