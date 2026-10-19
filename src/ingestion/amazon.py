"""Amazon Last-Mile ingestion: parse route/package/sequence JSON into tables.

Source: AWS Registry of Open Data, s3://amazon-last-mile-challenges/almrrc2021/
License: CC BY-NC 4.0. Training split: 6,112 routes, 2018, 5 US metros.
Real schemas (verified against the downloaded files):
  route_data.json:      {route_id: {station_code, date_YYYY_MM_DD,
                          departure_time_utc, executor_capacity_cm3,
                          route_score, stops: {stop_id: {lat, lng, type, zone_id}}}}
  package_data.json:    {route_id: {stop_id: {package_id:
                          {scan_status, time_window: {start_time_utc, end_time_utc},
                           planned_service_time_seconds,
                           dimensions: {depth_cm, height_cm, width_cm}}}}}
  actual_sequences.json:{route_id: {"actual": {stop_id: position}}}
travel_times.json (1.8 GB) is documented but not downloaded by default.
"""
import json
import os

import pandas as pd

from ..logging import get_logger

log = get_logger(__name__)

BASE_URL = ("https://amazon-last-mile-challenges.s3.amazonaws.com/"
            "almrrc2021/almrrc2021-data-training/model_build_inputs")

FILES = ["route_data.json", "package_data.json", "actual_sequences.json"]


def download(out_dir: str) -> list:
    import requests
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for name in FILES:
        url = f"{BASE_URL}/{name}"
        dest = os.path.join(out_dir, name)
        if os.path.exists(dest):
            log.info("exists, skipping: %s", dest)
        else:
            log.info("downloading %s", url)
            r = requests.get(url, timeout=300)
            r.raise_for_status()
            with open(dest, "wb") as f:
                f.write(r.content)
        paths.append(dest)
    return paths


def load_routes(path: str) -> tuple:
    """Returns (routes_df one row per route, stops_df one row per stop)."""
    with open(path) as f:
        raw = json.load(f)
    route_rows, stop_rows = [], []
    for route_id, r in raw.items():
        route_rows.append({
            "route_id": route_id,
            "station_code": r.get("station_code"),
            "date": r.get("date_YYYY_MM_DD"),
            "departure_time_utc": r.get("departure_time_utc"),
            "route_score": r.get("route_score"),
        })
        for stop_id, s in r["stops"].items():
            stop_rows.append({
                "route_id": route_id, "stop_id": stop_id,
                "lat": s["lat"], "lng": s["lng"],
                "zone_id": s.get("zone_id"), "type": s.get("type"),
            })
    routes = pd.DataFrame(route_rows)
    stops = pd.DataFrame(stop_rows)
    log.info("routes=%d stops=%d zones=%d",
             len(routes), len(stops), stops.zone_id.nunique())
    return routes, stops


def load_packages(path: str) -> pd.DataFrame:
    """One row per stop: package counts, volumes, time windows, service time."""
    with open(path) as f:
        raw = json.load(f)
    rows = []
    for route_id, stops in raw.items():
        for stop_id, packages in stops.items():
            vols, tw, svc = [], 0, []
            for pid, p in packages.items():
                d = p.get("dimensions") or {}
                vols.append(d.get("depth_cm", 0) * d.get("height_cm", 0)
                            * d.get("width_cm", 0) / 1e6)  # liters
                window = p.get("time_window") or {}
                if window.get("start_time_utc"):
                    tw += 1
                if p.get("planned_service_time_seconds"):
                    svc.append(p["planned_service_time_seconds"])
            rows.append({
                "route_id": route_id, "stop_id": stop_id,
                "n_packages": len(packages),
                "volume_liters": round(sum(vols), 2),
                "n_time_windows": tw,
                "planned_service_time_s": (round(sum(svc) / len(svc), 1)
                                           if svc else None),
            })
    df = pd.DataFrame(rows)
    log.info("package stops=%d", len(df))
    return df


def load_sequences(path: str) -> pd.DataFrame:
    """One row per route: ordered list of stop_ids as the driver drove them."""
    with open(path) as f:
        raw = json.load(f)
    rows = []
    for route_id, v in raw.items():
        ordered = sorted(v["actual"].items(), key=lambda kv: kv[1])
        rows.append({"route_id": route_id,
                     "actual_order": [s for s, _ in ordered]})
    return pd.DataFrame(rows)


def zone_fragmentation(stops: pd.DataFrame, sequences: pd.DataFrame) -> pd.DataFrame:
    """Zone transitions in the driver's actual order.

    A driver who leaves a zone and comes back later is doing extra travel.
    transitions = number of times consecutive stops are in different zones.
    revisits = zones visited more than once (non-contiguously).
    """
    zone_of = stops.set_index(["route_id", "stop_id"])["zone_id"].to_dict()
    out = []
    for _, row in sequences.iterrows():
        zones = [zone_of.get((row.route_id, s)) for s in row.actual_order]
        zones = [z for z in zones if z]
        transitions = sum(1 for a, b in zip(zones, zones[1:]) if a != b)
        seen, revisits = set(), 0
        # count zones appearing in more than one contiguous block
        blocks = [zones[0]] if zones else []
        for z in zones[1:]:
            if z != blocks[-1]:
                blocks.append(z)
        revisits = len(blocks) - len(set(blocks))
        out.append({"route_id": row.route_id, "n_stops": len(zones),
                    "zone_transitions": transitions, "zone_revisits": revisits})
    return pd.DataFrame(out)
