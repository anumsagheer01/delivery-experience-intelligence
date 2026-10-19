#!/usr/bin/env python3
"""Fetch remaining POD images directly from the official Open Images S3 mirror.

Reads remaining.csv (image_id,label,local_file,sha256), downloads each from
https://open-images-dataset.s3.amazonaws.com/train/{id}.jpg, verifies SHA256
and JPEG magic bytes, uploads verified images to GCS in groups, deletes local
copies. Idempotent: re-running re-downloads missing files; GCS objects are
only written after local verification.

Run under nohup: nohup python3 fetch_s3.py > fetch.log 2>&1 &
"""
import csv
import hashlib
import os
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

GCSB = "gs://dei-raw-67129202721/raw/vision/pod_dataset"
S3 = "https://open-images-dataset.s3.amazonaws.com/train"
WORK = os.path.expanduser("~/dei-data/stage2")
DL = os.path.join(WORK, "dl")
GROUP = 200
RETRIES = 3


def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "dei-research/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            f.write(chunk)


def good_jpeg(path):
    try:
        with open(path, "rb") as f:
            head = f.read(3)
        return head[:2] == b"\xff\xd8" and os.path.getsize(path) > 5000
    except OSError:
        return False


def download_one(args):
    """Download and verify one image. Returns (fname, True) or (iid, False)."""
    iid, label, fname, sha = args
    dest = os.path.join(DL, fname)
    for attempt in range(1, RETRIES + 1):
        try:
            fetch(f"{S3}/{iid}.jpg", dest)
            h = hashlib.sha256(open(dest, "rb").read()).hexdigest()
            if h == sha and good_jpeg(dest):
                return (fname, True)
        except Exception:
            pass
        time.sleep(3)
    return (iid, False)


def main():
    os.makedirs(DL, exist_ok=True)
    os.chdir(WORK)
    # Resumability: skip images already in GCS (survives VM restarts).
    print("listing existing GCS objects...", flush=True)
    ls = subprocess.run(["gsutil", "ls", GCSB + "/*.jpg"],
                        capture_output=True, text=True)
    existing = {u.rsplit("/", 1)[-1] for u in ls.stdout.split() if u.strip()}
    print(f"{len(existing)} already in GCS", flush=True)
    rows = [r for r in csv.reader(open("remaining.csv")) if r[2] not in existing]
    print(f"{len(rows)} images to fetch", flush=True)
    done, failed = 0, []
    batch = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        for fname_or_iid, ok in ex.map(download_one, rows):
            if ok:
                batch.append(fname_or_iid)
            else:
                failed.append(fname_or_iid)
                print(f"GIVING UP on {fname_or_iid}", flush=True)
            if len(batch) >= GROUP:
                print(f"uploading group of {len(batch)} to GCS...", flush=True)
                subprocess.run(["gsutil", "-m", "cp", "-n"] +
                               [os.path.join(DL, f) for f in batch] + [GCSB],
                               check=True)
                for f in batch:
                    os.remove(os.path.join(DL, f))
                done += len(batch)
                print(f"progress: {done} uploaded", flush=True)
                batch = []
    if batch:
        subprocess.run(["gsutil", "-m", "cp", "-n"] +
                       [os.path.join(DL, f) for f in batch] + [GCSB],
                       check=True)
        for f in batch:
            os.remove(os.path.join(DL, f))
        done += len(batch)
    print(f"FINISHED: {done} uploaded, {len(failed)} failed", flush=True)
    if failed:
        print("failed ids:", ",".join(failed), flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
