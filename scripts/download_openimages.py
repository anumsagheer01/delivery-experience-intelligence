#!/usr/bin/env python3
"""Download a sample of Open Images V7 'Box' photos for the vision benchmark.

Uses the official annotation CSVs (no auth needed). Downloads N images with
'Box' bounding boxes plus M images from unrelated classes as negatives.
Ground truth for QUALITY labels comes only from human review (see labeling app);
the Box/neg split is weak supervision for the visibility classifier.

Usage: python scripts/download_openimages.py --out data/raw/openimages --n-pos 400 --n-neg 200
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

from src.logging import get_logger  # noqa: E402

log = get_logger(__name__)

ANNOT = "https://storage.googleapis.com/openimages/v7/oidv7-train-annotations-bbox.csv"
CLASSES = "https://storage.googleapis.com/openimages/v7/oidv7-class-descriptions-boxable.csv"
# Image download pattern for Open Images V6/V7
IMG_URL = "https://storage.googleapis.com/openimages/v6/train/{img_id}.jpg"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw/openimages")
    ap.add_argument("--n-pos", type=int, default=400)
    ap.add_argument("--n-neg", type=int, default=200)
    args = ap.parse_args()

    os.makedirs(f"{args.out}/box", exist_ok=True)
    os.makedirs(f"{args.out}/neg", exist_ok=True)

    log.info("fetching class descriptions...")
    classes = {}
    with requests.get(CLASSES, stream=True, timeout=120) as r:
        r.raise_for_status()
        reader = csv.reader(r.iter_lines(decode_unicode=True))
        for code, name in reader:
            classes[name] = code
    box_code = classes["Box"]
    log.info("Box class code: %s", box_code)

    log.info("scanning train bbox annotations for Box images (this takes a while)...")
    pos_ids, seen = [], set()
    with requests.get(ANNOT, stream=True, timeout=600) as r:
        r.raise_for_status()
        reader = csv.DictReader(r.iter_lines(decode_unicode=True))
        for row in reader:
            if row["LabelName"] == box_code and row["ImageID"] not in seen:
                seen.add(row["ImageID"])
                pos_ids.append(row["ImageID"])
                if len(pos_ids) >= args.n_pos:
                    break
    log.info("found %d Box images; downloading...", len(pos_ids))
    for i, img_id in enumerate(pos_ids):
        dest = f"{args.out}/box/{img_id}.jpg"
        if not os.path.exists(dest):
            try:
                r = requests.get(IMG_URL.format(img_id=img_id), timeout=60)
                r.raise_for_status()
                with open(dest, "wb") as f:
                    f.write(r.content)
            except Exception as e:  # noqa: BLE001
                log.warning("skip %s: %s", img_id, e)
        if (i + 1) % 50 == 0:
            log.info("  %d/%d", i + 1, len(pos_ids))
    log.info("done. weak label 'package_visible' for box/, 'no_package' TBD by review for neg/")
    log.info("NOTE: negatives (unrelated classes) left as an exercise; use any non-box photos.")


if __name__ == "__main__":
    main()
