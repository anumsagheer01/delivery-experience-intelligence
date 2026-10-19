"""Unit tests: OSM feature extraction and leakage-safe labels."""
from src.address import extract_features


def sample_osm():
    return {"elements": [
        {"type": "node", "id": 1, "lat": -23.5, "lon": -46.6,
         "tags": {"shop": "bakery", "name": "Pao"}},
        {"type": "way", "id": 2, "center": {"lat": -23.51, "lon": -46.61},
         "tags": {"building": "house", "addr:housenumber": "10"}},
        {"type": "node", "id": 3, "lat": -23.52, "lon": -46.62,
         "tags": {"building": "yes"}},
    ]}


def test_labels():
    rows = extract_features(sample_osm())
    by_id = {r["osm_id"]: r for r in rows}
    assert by_id[1]["label"] == "business"
    assert by_id[2]["label"] == "residential"
    assert by_id[3]["label"] == "unknown"


def test_features_exclude_commercial_tags():
    rows = extract_features(sample_osm())
    for r in rows:
        assert "shop" not in r and "amenity" not in r  # leakage control
