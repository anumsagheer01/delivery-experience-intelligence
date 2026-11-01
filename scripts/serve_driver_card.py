"""Tiny standalone demo server for the driver card API.

SYNTHETIC DATA ONLY. Seeds the same demo stops as
scripts/demo_driver_intelligence.py and serves them locally.
Requires fastapi and uvicorn (already in requirements.txt).
No GCP credentials, no network calls to GCP.

Run from the repo root:
  python scripts/serve_driver_card.py
Then open http://127.0.0.1:8000/driver/card/stop_apt_101?driver_id=driver_demo_1
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo_driver_intelligence import seed  # noqa: E402
from src.driver_intelligence.agent import DriverAgent  # noqa: E402
from src.driver_intelligence.card_api import build_app  # noqa: E402
from src.driver_intelligence.memory import StopMemoryStore  # noqa: E402

# Note: importing demo_driver_intelligence only reuses its seed function;
# running this file as a script does not run the demo itself.


def main():
    store = StopMemoryStore()
    seed(store)
    agent = DriverAgent(store, llm_summarizer=None)
    app = build_app(store, agent)
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
