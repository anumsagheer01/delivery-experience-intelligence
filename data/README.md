# Data directory

`data/raw/` is intentionally empty in this repository.

## Why

The datasets are large (hundreds of MB) and carry their own licenses
(CC BY-NC 4.0, ODbL, CC BY 4.0). Raw data is never committed. Instead, every
dataset has a reproducible acquisition script under `scripts/` that downloads
from the official public source:

| Dataset | Script | Source |
|---|---|---|
| Olist | `scripts/download_olist.py` | github.com/olist/work-at-olist-data (official Olist repo) |
| Amazon Last-Mile | `scripts/download_amazon.py` | AWS Registry of Open Data, s3://amazon-last-mile-challenges |
| Open Images (Box class) | `scripts/download_openimages.py` | storage.googleapis.com/openimages |
| OSM sample | `scripts/download_osm.py` | Overpass API (openstreetmap.org) |

## Manifests

`data/manifests/` records SHA256 checksums, row counts, and download dates for
every acquired file, so any run can be traced back to exact bytes. See
`src/ingestion/manifest.py`.
