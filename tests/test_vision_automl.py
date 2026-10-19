"""Tests for src/vision/automl.py scoring and assessment logic.

Uses tiny synthetic prediction lines and a synthetic manifest; asserts
the confusion math, the malformed-line guard, and the PodAssessor
unknown-URI behavior (must be assessed=False, never a silent negative).
"""
import csv
import json
import os
import tempfile
import unittest

from src.vision.automl import (PodAssessor, parse_prediction_line,
                               score_predictions)


def _pred(uri, names, scores):
    return json.dumps({"content": uri,
                       "prediction": {"displayNames": names,
                                      "confidences": scores}})


class TestParsePredictionLine(unittest.TestCase):
    def test_argmax(self):
        p = parse_prediction_line(
            _pred("gs://b/a.jpg", ["door_no_package", "package_present"],
                  [0.2, 0.8]))
        self.assertEqual(p["predicted_label"], "package_present")
        self.assertAlmostEqual(p["confidence"], 0.8)

    def test_malformed_raises(self):
        for bad in ['{"content": "gs://b/a.jpg"}',
                    _pred("gs://b/a.jpg", ["a"], [0.5, 0.6]),
                    "not json"]:
            with self.assertRaises(ValueError):
                parse_prediction_line(bad)


class TestScorePredictions(unittest.TestCase):
    def _manifest(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["image_id", "label", "ml_use", "gcs_uri",
                        "local_file", "sha256"])
            w.writerow(["a1", "door_no_package", "TEST", "gs://b/a1.jpg",
                        "a1.jpg", "h1"])
            w.writerow(["a2", "package_present", "TEST", "gs://b/a2.jpg",
                        "a2.jpg", "h2"])
            w.writerow(["a3", "package_present", "TRAIN", "gs://b/a3.jpg",
                        "a3.jpg", "h3"])
        return path

    def test_confusion_math(self):
        path = self._manifest()
        lines = [
            _pred("gs://b/a1.jpg", ["door_no_package", "package_present"],
                  [0.9, 0.1]),   # tn
            _pred("gs://b/a2.jpg", ["door_no_package", "package_present"],
                  [0.7, 0.3]),   # fn (actual package, predicted door)
            _pred("gs://b/a3.jpg", ["door_no_package", "package_present"],
                  [0.1, 0.9]),   # TRAIN row: ignored
            _pred("gs://b/zz.jpg", ["door_no_package", "package_present"],
                  [0.9, 0.1]),   # unmatched uri
        ]
        m = score_predictions(lines, path)
        self.assertEqual(m["n"], 2)
        self.assertEqual(m["unmatched"], 2)  # TRAIN-row + unknown URI
        self.assertEqual(m["confusion"], [[1, 0], [1, 0]])
        self.assertAlmostEqual(m["accuracy"], 0.5)
        self.assertEqual(m["door_no_package"]["support"], 1)
        os.remove(path)


class TestPodAssessor(unittest.TestCase):
    def test_known_and_unknown(self):
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w") as f:
            f.write(_pred("gs://b/a.jpg",
                          ["door_no_package", "package_present"],
                          [0.05, 0.95]) + "\n")
        a = PodAssessor(path)
        r = a.assess("gs://b/a.jpg")
        self.assertTrue(r["assessed"])
        self.assertTrue(r["package_visible"])
        self.assertAlmostEqual(r["confidence"], 0.95)
        r2 = a.assess("gs://b/missing.jpg")
        self.assertFalse(r2["assessed"])
        self.assertIsNone(r2["package_visible"])
        os.remove(path)


if __name__ == "__main__":
    unittest.main()
