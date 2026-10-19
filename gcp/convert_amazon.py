#!/usr/bin/env python3
"""Convert ALMRRC JSON dicts to newline-delimited JSON for BigQuery loading.

Reads route_data.json, package_data.json, actual_sequences.json from IN_DIR
and writes routes.ndjson, stops.ndjson, packages.ndjson, sequences.ndjson
to OUT_DIR. Mirrors the parsing logic of the project's local ingestion
(src/ingestion/amazon.py) so cloud tables match local analysis exactly.
"""
import json
import os
import sys

IN_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/dei-data/amazon")
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser("~/dei-data/amazon_ndjson")
os.makedirs(OUT_DIR, exist_ok=True)


def write_ndjson(path, rows):
    n = 0
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
            n += 1
    print(f"wrote {path}: {n} rows")
    return n


with open(os.path.join(IN_DIR, "route_data.json")) as f:
    raw_routes = json.load(f)

route_rows, stop_rows = [], []
for route_id, r in raw_routes.items():
    route_rows.append({
        "route_id": route_id,
        "station_code": r.get("station_code"),
        "date": r.get("date_YYYY_MM_DD"),
        "departure_time_utc": r.get("departure_time_utc"),
        "route_score": r.get("route_score"),
    })
    for stop_id, s in r["stops"].items():
        stop_rows.append({
            "route_id": route_id,
            "stop_id": stop_id,
            "lat": s.get("lat"),
            "lng": s.get("lng"),
            "zone_id": s.get("zone_id"),
            "type": s.get("type"),
        })

with open(os.path.join(IN_DIR, "package_data.json")) as f:
    raw_packages = json.load(f)

package_rows = []
for route_id, stops in raw_packages.items():
    for stop_id, packages in stops.items():
        vols, tw, svc = [], 0, []
        for pid, p in packages.items():
            d = p.get("dimensions") or {}
            vols.append(d.get("depth_cm", 0) * d.get("height_cm", 0)
                        * d.get("width_cm", 0) / 1e6)
            window = p.get("time_window") or {}
            if window.get("start_time_utc"):
                tw += 1
            if p.get("planned_service_time_seconds"):
                svc.append(p["planned_service_time_seconds"])
        package_rows.append({
            "route_id": route_id,
            "stop_id": stop_id,
            "n_packages": len(packages),
            "volume_liters": round(sum(vols), 2),
            "n_time_windows": tw,
            "planned_service_time_s": (round(sum(svc) / len(svc), 1) if svc else None),
        })

with open(os.path.join(IN_DIR, "actual_sequences.json")) as f:
    raw_seq = json.load(f)

seq_rows = []
for route_id, seq in raw_seq.items():
    stops = seq.get("actual") if isinstance(seq, dict) else seq
    seq_rows.append({"route_id": route_id, "actual_stops": list(stops or [])})

write_ndjson(os.path.join(OUT_DIR, "routes.ndjson"), route_rows)
write_ndjson(os.path.join(OUT_DIR, "stops.ndjson"), stop_rows)
write_ndjson(os.path.join(OUT_DIR, "packages.ndjson"), package_rows)
write_ndjson(os.path.join(OUT_DIR, "sequences.ndjson"), seq_rows)
print("conversion complete")
