"""Classical vision baselines: blur and brightness on real package photos.

Blur: variance of the Laplacian (lower = blurrier). Brightness: mean grayscale
intensity. No training, no API calls. Every learned approach must beat these;
a baseline that wins a slice is a finding, not a failure.
"""
import csv
import os
from collections import defaultdict

import cv2

from ..logging import get_logger

log = get_logger(__name__)


def blur_score(path: str) -> float:
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def brightness(path: str) -> float:
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(path)
    return float(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).mean())


def score_images(image_paths: list) -> list:
    rows = []
    for p in image_paths:
        try:
            rows.append({"image": p, "laplacian_var": round(blur_score(p), 1),
                         "brightness": round(brightness(p), 1)})
        except Exception as e:  # noqa: BLE001 - keep batch running, log it
            log.warning("skipping %s: %s", p, e)
    return rows


def summarize_by_label(scored: list, labels: dict) -> dict:
    """labels: image path -> human label. Prints per-label distributions."""
    dist = defaultdict(list)
    for r in scored:
        if r["image"] in labels:
            dist[labels[r["image"]]].append((r["laplacian_var"], r["brightness"]))
    summary = {}
    for lab, vals in sorted(dist.items()):
        bs = [v[0] for v in vals]
        br = [v[1] for v in vals]
        summary[lab] = {"n": len(vals),
                        "mean_blur": round(sum(bs) / len(bs), 1),
                        "mean_brightness": round(sum(br) / len(br), 1)}
    return summary


def write_csv(rows: list, out_path: str):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["image", "laplacian_var", "brightness"])
        w.writeheader()
        w.writerows(rows)
    log.info("wrote %d scored images -> %s", len(rows), out_path)
