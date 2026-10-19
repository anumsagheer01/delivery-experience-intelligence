#!/usr/bin/env python3
"""Build the final GitHub deliverable ZIP.

Excludes: Python caches, virtualenvs, git metadata, raw datasets,
build artifacts, and anything secret-like. Everything else ships,
including src/agents, .github/workflows, gcp/ scripts, evals/,
and data/vision/ manifests.
"""
import os
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.expanduser(
    "~/workspace/your_files/delivery-experience-intelligence-github.zip")

EXCLUDE_DIRS = {
    "__pycache__", ".venv", "venv", ".git", ".pytest_cache",
    "node_modules", "data/raw",
}
EXCLUDE_FILES = {".env"}
EXCLUDE_EXT = {".pyc", ".pyo"}
SECRET_HINTS = ("service-account", "kaggle.json", ".pem", "id_rsa",
                "credentials", ".key")


def excluded(rel: str) -> bool:
    parts = rel.split(os.sep)
    if any(d in EXCLUDE_DIRS for d in parts):
        return True
    base = os.path.basename(rel)
    if base in EXCLUDE_FILES:
        return True
    if os.path.splitext(base)[1] in EXCLUDE_EXT:
        return True
    low = rel.lower()
    if any(h in low for h in SECRET_HINTS):
        return True
    return False


def main() -> None:
    n = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(REPO):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
            for fn in sorted(files):
                p = os.path.join(root, fn)
                rel = os.path.relpath(p, REPO)
                if excluded(rel):
                    continue
                z.write(p, rel)
                n += 1
    size = os.path.getsize(OUT)
    print(f"github zip: {n} files -> {OUT} ({size} bytes)")


if __name__ == "__main__":
    main()
