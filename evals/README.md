# Evaluation outputs

Every file here was produced by running the code in this repo against real
data. Provenance:

- `risk/` : `python -m src.ml` training outputs (JSON metrics per model).
  See `scripts/` for the exact commands. Splits and features are documented
  in `src/ml/__init__.py`.
- `vision/` : `evals/vision/opencv_baselines.csv` from
  `src/vision/__init__.py` on 100 real Open Images photos.
- `agent/` : `scripts/eval_agent.py` dry-run results on 5 controlled
  scenarios.

Nothing in this directory is hand-written or estimated.
