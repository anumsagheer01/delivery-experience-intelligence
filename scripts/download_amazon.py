#!/usr/bin/env python3
"""Download Amazon Last-Mile training files from the AWS Open Data Registry.

Usage: python scripts/download_amazon.py --out data/raw/amazon [--skip-travel-times]
travel_times.json is 1.8 GB and skipped by default; pass --with-travel-times to fetch it.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingestion import write_manifest
from src.ingestion.amazon import BASE_URL, download

LICENSE = "CC BY-NC 4.0 (https://creativecommons.org/licenses/by-nc/4.0/)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw/amazon")
    ap.add_argument("--with-travel-times", action="store_true")
    args = ap.parse_args()
    paths = download(args.out)
    if args.with_travel_times:
        import requests
        url = f"{BASE_URL}/travel_times.json"
        dest = os.path.join(args.out, "travel_times.json")
        print(f"downloading {url} (1.8 GB)...")
        r = requests.get(url, timeout=600)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
        paths.append(dest)
    else:
        print("skipped travel_times.json (1.8 GB); use --with-travel-times to fetch")
    entries = [{"file": p,
                "source_url": "s3://amazon-last-mile-challenges/almrrc2021",
                "license": LICENSE, "notes": "2021 Amazon Last Mile Routing Research Challenge"}
               for p in paths]
    write_manifest(os.path.join(args.out, "..", "manifests"), entries)


if __name__ == "__main__":
    main()
