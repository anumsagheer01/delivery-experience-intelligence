#!/usr/bin/env python3
"""Verify the 85 Flickr-original images against manifest.csv and upload to GCS.

Fixes the CRLF bug in upload_flickr85.sh (awk+grep exact-line match failed
when manifest.csv carries \\r line endings). This script parses the CSV
properly and compares hex digests directly.

Prereqs in Cloud Shell: ~/dei-data/stage2/flickr85/ holds the 85 extracted
jpgs; ~/dei-data/stage2/manifest.csv present.
Usage: cd ~/dei-data/stage2 && python3 verify_upload_flickr85.py
"""
import csv
import hashlib
import os
import subprocess
import sys

STAGE = os.path.expanduser("~/dei-data/stage2")
IMGDIR = os.path.join(STAGE, "flickr85")
GCSB = "gs://dei-raw-67129202721/raw/vision/pod_dataset"

want = {}
with open(os.path.join(STAGE, "manifest.csv"), newline="") as f:
    for row in csv.reader(f):
        if not row or row[0] == "image_id":
            continue
        # columns: image_id,label,ml_use,gcs_uri,local_file,sha256
        want[row[4].strip()] = row[5].strip()

ok, bad = [], []
for fn in sorted(os.listdir(IMGDIR)):
    if not fn.endswith(".jpg"):
        continue
    p = os.path.join(IMGDIR, fn)
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    if fn in want and h == want[fn]:
        ok.append(fn)
    else:
        bad.append(fn)
print(f"verified: {len(ok)} ok, {len(bad)} bad", flush=True)
if bad:
    print("BAD_FILES:", bad)
    sys.exit(1)

for i in range(0, len(ok), 25):
    chunk = [os.path.join(IMGDIR, c) for c in ok[i:i + 25]]
    subprocess.run(["gsutil", "-m", "cp", "-n"] + chunk + [GCSB + "/"],
                   check=True, timeout=600)
    print(f"uploaded {min(i+25, len(ok))}/{len(ok)}", flush=True)
print("UPLOAD_DONE")
