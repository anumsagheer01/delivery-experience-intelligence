"""FastAPI demo endpoints: health, metrics, and agent dry-run."""
from fastapi import FastAPI

app = FastAPI(title="Delivery Experience Intelligence API")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics/late-delivery")
def late_delivery():
    # served from precomputed evals; see evals/risk/
    return {"note": "see evals/risk/is_late__hgb.json for measured metrics"}


@app.post("/agent/dry-run")
def agent_dry_run(event: dict):
    from src.agents import handle_event
    return handle_event(event, context={}, dry_run=True)
