# Vision dataset manifests

Small metadata files for the 4,712-image proof-of-delivery dataset.
The images themselves live in GCS
(`gs://dei-raw-67129202721/raw/vision/pod_dataset/`), not in this repo.

| File | Contents |
| --- | --- |
| `manifest.csv` | All 4,712 images: image ID, label, split (TRAIN/VALIDATION/TEST), GCS URI, local filename, SHA256 |
| `automl_import.csv` | Vertex AI import manifest: GCS URI, label, ML_USE |
| `manifest_provenance.json` | Dual-source provenance note (4,627 S3-mirror 1024px + 85 Flickr full-resolution originals) |
| `audit_sample.json` | The 250-image manual audit sample |

The full dataset build scripts (download, dedupe, split, montage audit)
are documented in `docs/decisions/vision_model.md`.
