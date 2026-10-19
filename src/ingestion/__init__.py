"""Data manifests: SHA256, row counts, and provenance for every acquired file.

Every pipeline run records exactly which bytes it consumed. This is what makes
results reproducible and auditable.
"""
import csv
import hashlib
import json
import os
from datetime import datetime, timezone

from ..logging import get_logger

log = get_logger(__name__)


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def count_rows_csv(path: str) -> int:
    with open(path, newline="", encoding="utf-8") as f:
        return sum(1 for _ in f) - 1  # minus header


def write_manifest(out_dir: str, entries: list) -> str:
    """entries: list of dicts with file, source_url, license, notes."""
    os.makedirs(out_dir, exist_ok=True)
    stamped = []
    for e in entries:
        full = os.path.join(out_dir, "..", e["file"]) if False else e["file"]
        row = dict(e)
        row["sha256"] = sha256_of(e["file"]) if os.path.exists(e["file"]) else None
        row["recorded_at"] = datetime.now(timezone.utc).isoformat()
        stamped.append(row)
    path = os.path.join(out_dir, "manifest.json")
    with open(path, "w") as f:
        json.dump(stamped, f, indent=2)
    log.info("wrote manifest with %d entries -> %s", len(stamped), path)
    return path


def check_manifest(manifest_path: str) -> bool:
    """Verify every file still matches its recorded checksum."""
    ok = True
    with open(manifest_path) as f:
        for e in json.load(f):
            if not os.path.exists(e["file"]):
                log.error("missing file: %s", e["file"])
                ok = False
                continue
            if sha256_of(e["file"]) != e["sha256"]:
                log.error("checksum mismatch: %s", e["file"])
                ok = False
    log.info("manifest check: %s", "OK" if ok else "FAILED")
    return ok
