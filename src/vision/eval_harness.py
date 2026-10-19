"""Vision evaluation harness: score one fixed benchmark with every approach.

Approaches (each implements score(image_path) -> dict):
  opencv   : blur/brightness baselines (runs anywhere)
  automl   : Vertex AI AutoML endpoint (needs GCP)
  vision   : Cloud Vision API labels (needs GCP)
  gemini   : Gemini structured SOP verdict (needs GEMINI_API_KEY)

Fairness rules: same images, same labels for everyone. Baselines and learned
models are compared on the SAME task (package_visible). Gemini's SOP verdict
is a richer task; report it separately, not as a single-number ranking.
"""
import csv
import json
import os

from . import blur_score, brightness
from ..logging import get_logger

log = get_logger(__name__)


def opencv_score(image_path: str) -> dict:
    b, br = blur_score(image_path), brightness(image_path)
    return {"approach": "opencv", "laplacian_var": b, "brightness": br,
            "package_visible": b > 50.0 and br > 25.0}  # documented heuristic


GEMINI_PROMPT = """You are a delivery quality inspector. Look at this
proof-of-delivery photo and return JSON only:
{"package_visible": true/false, "quality": "good|package_obscured|blurry|wrong_location|unsafe_placement|low_light|no_package", "confidence": 0.0-1.0, "rationale": "one sentence"}
A POD photo must show the delivered package at the customer's door."""


def gemini_score(image_path: str, model: str = "gemini-2.0-flash") -> dict:
    """Needs google-generativeai + GEMINI_API_KEY. Strict JSON schema."""
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    with open(image_path, "rb") as f:
        img = {"mime_type": "image/jpeg", "data": f.read()}
    resp = genai.GenerativeModel(model).generate_content([GEMINI_PROMPT, img])
    return {"approach": "gemini",
            **json.loads(resp.text.strip().strip("`"))}


def evaluate(images: list, labels: dict, scorer, out_path: str) -> dict:
    """labels: image -> human label string. Returns confusion-style summary."""
    tp = fp = tn = fn = skipped = 0
    rows = []
    for img in images:
        if img not in labels:
            continue
        try:
            r = scorer(img)
        except Exception as e:  # noqa: BLE001
            skipped += 1
            log.warning("scorer failed on %s: %s", img, e)
            continue
        truth = labels[img] != "no_package"
        pred = bool(r.get("package_visible"))
        tp += truth and pred
        fp += (not truth) and pred
        tn += (not truth) and (not pred)
        fn += truth and (not pred)
        rows.append({"image": img, "truth": truth, "pred": pred})
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    summary = {"n": tp + fp + tn + fn, "skipped": skipped,
               "precision": round(precision, 4), "recall": round(recall, 4),
               "f1": round(2 * precision * recall / max(precision + recall, 1e-9), 4),
               "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn}}
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"summary": summary, "rows": rows}, f, indent=2)
    log.info("eval: %s", summary)
    return summary
