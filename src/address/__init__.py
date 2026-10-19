"""Address intelligence: OSM feature extraction and business-vs-residential labels.

Leakage control (the critical design point): labels come from commercial-activity
tags (shop/amenity/office/craft). Model features must EXCLUDE those tags
(geometry + addressing tags only). Otherwise the model memorizes the labeling
rule and reports meaningless accuracy.

Two data paths:
  bigquery : planet-scale via bigquery-public-data.geo_openstreetmap (needs GCP)
  overpass : small real sample via the Overpass API (runs anywhere, used here)
"""
import json

import requests

from ..logging import get_logger

log = get_logger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
COMMERCIAL_KEYS = {"shop", "amenity", "office", "craft"}
RESIDENTIAL_BUILDINGS = {"house", "residential", "apartments", "detached",
                         "terrace", "semidetached_house"}


def fetch_overpass(bbox: str, timeout: int = 120) -> dict:
    """bbox: 'south,west,north,east'. Returns Overpass JSON of buildings/POIs."""
    query = f"""
    [out:json][timeout:{timeout}];
    (node["shop"]({bbox}); node["amenity"]({bbox}); node["office"]({bbox});
     way["building"]({bbox}););
    out center tags;
    """
    log.info("querying Overpass API for bbox %s", bbox)
    r = requests.get(OVERPASS_URL, params={"data": query}, timeout=timeout + 30)
    r.raise_for_status()
    return r.json()


def extract_features(osm_json: dict) -> list:
    """One feature row per OSM element, with leakage-safe label."""
    rows = []
    for el in osm_json.get("elements", []):
        tags = el.get("tags", {})
        commercial = sum(1 for k in tags if k in COMMERCIAL_KEYS)
        building = tags.get("building")
        if commercial > 0:
            label = "business"          # confident business
        elif building in RESIDENTIAL_BUILDINGS:
            label = "residential"       # confident residential
        else:
            label = "unknown"           # ambiguous: kept as explicit category
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        rows.append({
            "osm_id": el["id"],
            "osm_type": el["type"],
            "lat": lat, "lon": lon,
            "label": label,
            # features (no commercial-activity tags):
            "has_housenumber": int("addr:housenumber" in tags),
            "has_name": int("name" in tags),
            "has_opening_hours": int("opening_hours" in tags),
            "n_tags": len(tags),
            "is_building": int("building" in tags),
        })
    log.info("extracted %d OSM elements", len(rows))
    return rows


def summarize(rows: list) -> dict:
    from collections import Counter
    c = Counter(r["label"] for r in rows)
    return {"n": len(rows), "labels": dict(c)}


def parse_osm_xml(path: str, max_elements: int = 0) -> list:
    """Stream-parse an .osm (XML, optionally gzipped) extract.

    Two passes: (1) collect tagged nodes and ways with their node refs;
    (2) resolve coordinates only for referenced nodes. Returns leakage-safe
    feature rows (same schema as extract_features). Ways use their first
    node's coordinates as an approximate location.
    """
    import gzip
    import xml.etree.ElementTree as ET

    opener = gzip.open if path.endswith(".gz") else open
    tagged_nodes, tagged_ways = [], []

    def tags_of(elem):
        return {t.get("k"): t.get("v") for t in elem.findall("tag")}

    def relevant(tags):
        return bool(tags.get("building")
                    or any(k in tags for k in COMMERCIAL_KEYS))

    def label_of(tags):
        commercial = sum(1 for k in tags if k in COMMERCIAL_KEYS)
        if commercial > 0:
            return "business"
        if tags.get("building") in RESIDENTIAL_BUILDINGS:
            return "residential"
        return "unknown"

    def row(osm_id, etype, lat, lon, tags):
        return {
            "osm_id": osm_id, "osm_type": etype, "lat": lat, "lon": lon,
            "label": label_of(tags),
            "has_housenumber": int("addr:housenumber" in tags),
            "has_name": int("name" in tags),
            "has_opening_hours": int("opening_hours" in tags),
            "n_tags": len(tags),
            "is_building": int("building" in tags),
        }

    # pass 1: tagged nodes (with coords) and tagged ways (with node refs)
    # NOTE: only node/way elements are cleared; clearing child <tag>/<nd>
    # elements at their own end-events would wipe their attributes.
    with opener(path, "rb") as f:
        for _, elem in ET.iterparse(f, events=("end",)):
            if elem.tag == "node":
                tags = tags_of(elem)
                if relevant(tags):
                    tagged_nodes.append((
                        int(elem.get("id")), float(elem.get("lat")),
                        float(elem.get("lon")), tags))
                elem.clear()
            elif elem.tag == "way":
                tags = tags_of(elem)
                if relevant(tags):
                    tagged_ways.append((
                        int(elem.get("id")),
                        [int(nd.get("ref")) for nd in elem.findall("nd")],
                        tags))
                elem.clear()
    log.info("pass 1: %d tagged nodes, %d tagged ways",
             len(tagged_nodes), len(tagged_ways))

    # pass 2: coordinates for nodes referenced by tagged ways
    need = {ref for _, refs, _ in tagged_ways for ref in refs[:1]}
    coords = {}
    with opener(path, "rb") as f:
        for _, elem in ET.iterparse(f, events=("end",)):
            if elem.tag == "node":
                nid = int(elem.get("id"))
                if nid in need:
                    coords[nid] = (float(elem.get("lat")), float(elem.get("lon")))
                    if len(coords) >= len(need):
                        break
                elem.clear()
            elif elem.tag == "way":
                elem.clear()

    rows = [row(nid, "node", lat, lon, tags)
            for nid, lat, lon, tags in tagged_nodes]
    for wid, refs, tags in tagged_ways:
        if refs and refs[0] in coords:
            lat, lon = coords[refs[0]]
            rows.append(row(wid, "way", lat, lon, tags))
    if max_elements:
        rows = rows[:max_elements]
    log.info("parsed %d labeled OSM elements from %s", len(rows), path)
    return rows
