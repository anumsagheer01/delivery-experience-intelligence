#!/usr/bin/env python3
"""Download Olist from the official Olist GitHub mirror + write manifest.

Usage: python scripts/download_olist.py --out data/raw/olist
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingestion import write_manifest
from src.ingestion.olist import FILES, download

LICENSE = "https://github.com/olist/work-at-olist-data (see repo LICENSE; attribution required)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw/olist")
    args = ap.parse_args()
    paths = download(args.out)
    entries = [{"file": p,
                "source_url": "https://github.com/olist/work-at-olist-data",
                "license": LICENSE,
                "notes": "official Olist repo mirror of the Kaggle dataset"}
               for p in paths]
    write_manifest(os.path.join(args.out, "..", "manifests"), entries)


if __name__ == "__main__":
    main()
