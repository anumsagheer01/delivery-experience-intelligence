#!/bin/bash
# Stage 3 (Cloud Shell): verify GCS -> BQ table -> Vertex AI dataset ->
# CSV import -> AutoML training launch (MANAGED training pipeline: runs
# server-side, independent of Cloud Shell).
# Approved 2026-10-17: budget 8000 milli node-hours (~$27.72 gross, ceiling $35).
# Rev 2026-10-18 (REST): steps 3-5 use the Vertex AI REST API via curl because
# this Cloud Shell's gcloud has no `ai datasets` subcommand.
# Rev 2026-10-18b: step 5 fixed — dataset goes in inputDataConfig.datasetId
# (a top-level "dataset" field does not exist on TrainingPipeline); api_post
# hardened against non-JSON responses; steps 3/4/5 are idempotent on re-run
# (reuse existing dataset / skip completed import / reuse existing pipeline).
# Usage: bash stage3.sh  (run under nohup; polls the CSV import)
set -euo pipefail
PROJECT=delivery-experience-511901
REGION=us-central1
GCSB=gs://dei-raw-67129202721/raw/vision/pod_dataset
APIBASE="https://us-central1-aiplatform.googleapis.com/v1"
cd ~/dei-data/stage2

get_token() { gcloud auth print-access-token; }

# POST JSON; prints response body. Returns 1 (loudly) on API or parse errors.
api_post() { # $1=url $2=datafile
  local TOKEN resp err
  TOKEN=$(get_token)
  resp=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" "$1" -d @"$2")
  if ! echo "$resp" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
    echo "API ERROR (non-JSON response) calling $1:" >&2
    echo "$resp" | head -c 2000 >&2; echo >&2
    return 1
  fi
  err=$(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); e=d.get('error') or {}; print(e.get('message',''))")
  if [ -n "$err" ]; then
    echo "API ERROR calling $1:" >&2
    echo "$err" >&2
    return 1
  fi
  echo "$resp"
}

# GET JSON, fail-open to empty string on any problem (used for idempotency checks)
api_get() { # $1=url
  local TOKEN
  TOKEN=$(get_token)
  curl -s -H "Authorization: Bearer $TOKEN" "$1" 2>/dev/null || true
}

# Poll a long-running operation name until done; prints response.name (may be
# empty for import). Fails on operation error or timeout (60 min).
poll_operation() { # $1=operation resource name
  local op="$1" i resp done_flag has_err
  for i in $(seq 1 120); do
    resp=$(api_get "$APIBASE/$op")
    done_flag=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('done', False))" 2>/dev/null || echo "PARSE_FAIL")
    if [ "$done_flag" = "PARSE_FAIL" ]; then echo "could not parse operation status, retrying..."; sleep 30; continue; fi
    if [ "$done_flag" = "True" ]; then
      has_err=$(echo "$resp" | python3 -c "import sys,json; print('yes' if json.load(sys.stdin).get('error') else 'no')")
      if [ "$has_err" = "yes" ]; then
        echo "OPERATION FAILED: $op" >&2
        echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['error'])" >&2
        return 1
      fi
      echo "$resp" | python3 -c "import sys,json; print((json.load(sys.stdin).get('response') or {}).get('name',''))"
      return 0
    fi
    sleep 30
  done
  echo "OPERATION TIMED OUT after 60 min: $op" >&2
  return 1
}

echo "=== 1/5 verify GCS ==="
N=$(gsutil ls "$GCSB/*.jpg" | wc -l)
echo "gcs jpgs: $N (expect 4712)"
[ "$N" -eq 4712 ] || { echo "COUNT MISMATCH, aborting"; exit 1; }
gsutil ls "$GCSB/automl_import.csv" > /dev/null
gsutil ls "$GCSB/manifest.csv" > /dev/null
gsutil ls "$GCSB/manifest_provenance.json" > /dev/null
echo "manifest files present"

echo "=== 2/5 BigQuery experiment_exposures table ==="
bq query --use_legacy_sql=false --project_id="$PROJECT" < experiment_exposures.sql
echo "table ready"

echo "=== 3/5 Vertex AI dataset (REST, idempotent) ==="
EXISTING_DS=$(api_get "$APIBASE/projects/$PROJECT/locations/$REGION/datasets?pageSize=20" \
  | python3 -c "
import sys,json
try:
    ds=[d['name'] for d in json.load(sys.stdin).get('datasets',[]) if d.get('displayName')=='dei-pod-photos-v1']
    print(ds[0] if ds else '')
except Exception:
    print('')" 2>/dev/null || true)
if [ -n "$EXISTING_DS" ]; then
  DS_FULL="$EXISTING_DS"
  echo "reusing existing dataset: $DS_FULL"
else
  cat > /tmp/dei_ds.json <<'EOF'
{"displayName":"dei-pod-photos-v1","metadataSchemaUri":"gs://google-cloud-aiplatform/schema/dataset/metadata/image_1.0.0.yaml"}
EOF
  RESP=$(api_post "$APIBASE/projects/$PROJECT/locations/$REGION/datasets" /tmp/dei_ds.json) || exit 1
  OP=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['name'])")
  echo "create op: $OP"
  DS_FULL=$(poll_operation "$OP")
  [ -n "$DS_FULL" ] || { echo "DATASET CREATE FAILED (empty name)"; exit 1; }
fi
DS_ID=$(basename "$DS_FULL")
echo "dataset id: $DS_ID"
echo "$DS_ID" > vertex_dataset_id.txt
gsutil cp vertex_dataset_id.txt "$GCSB/"

echo "=== 4/5 import CSV (REST, polling, idempotent) ==="
HAS_ITEMS=$(api_get "$APIBASE/$DS_FULL/dataItems?pageSize=1" \
  | python3 -c "
import sys,json
try:
    print(len(json.load(sys.stdin).get('dataItems',[])))
except Exception:
    print(0)" 2>/dev/null || echo 0)
if [ "$HAS_ITEMS" -gt 0 ]; then
  echo "data items already imported, skipping"
else
  cat > /tmp/dei_import.json <<EOF
{"importConfigs":[{"gcsSource":{"uris":["$GCSB/automl_import.csv"]},"importSchemaUri":"gs://google-cloud-aiplatform/schema/dataset/ioformat/image_classification_single_label_io_format_1.0.0.yaml"}]}
EOF
  RESP=$(api_post "$APIBASE/$DS_FULL:import" /tmp/dei_import.json) || exit 1
  OP=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['name'])")
  echo "import op: $OP"
  poll_operation "$OP" > /dev/null
  echo "import done"
fi

echo "=== 5/5 launch AutoML training (managed pipeline, REST, idempotent) ==="
EXISTING_PIPE=$(api_get "$APIBASE/projects/$PROJECT/locations/$REGION/trainingPipelines?pageSize=20" \
  | python3 -c "
import sys,json
try:
    ps=[p['name'] for p in json.load(sys.stdin).get('trainingPipelines',[]) if p.get('displayName')=='dei-pod-automl-v1']
    print(ps[0] if ps else '')
except Exception:
    print('')" 2>/dev/null || true)
if [ -n "$EXISTING_PIPE" ]; then
  PIPE="$EXISTING_PIPE"
  echo "reusing existing pipeline: $PIPE"
else
  cat > /tmp/dei_pipe.json <<EOF
{"displayName":"dei-pod-automl-v1",
 "trainingTaskDefinition":"gs://google-cloud-aiplatform/schema/trainingjob/definition/automl_image_classification_1.0.0.yaml",
 "trainingTaskInputs":{"modelType":"CLOUD","budgetMilliNodeHours":"8000","multiLabel":false},
 "inputDataConfig":{"datasetId":"$DS_ID"},
 "modelToUpload":{"displayName":"dei-pod-automl-v1"}}
EOF
  RESP=$(api_post "$APIBASE/projects/$PROJECT/locations/$REGION/trainingPipelines" /tmp/dei_pipe.json) || exit 1
  PIPE=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('name',''))")
  [ -n "$PIPE" ] || { echo "PIPELINE CREATE FAILED"; exit 1; }
fi
echo "training pipeline: $PIPE"
echo "$PIPE" > vertex_pipeline.txt
gsutil cp vertex_pipeline.txt "$GCSB/"
PIPE_ID=$(basename "$PIPE")
echo "console: https://console.cloud.google.com/vertex-ai/locations/$REGION/training-pipelines/$PIPE_ID?project=$PROJECT"
echo "STAGE3_DONE"
