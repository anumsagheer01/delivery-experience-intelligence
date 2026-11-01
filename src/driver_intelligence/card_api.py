"""Driver card API: a mountable FastAPI router plus HTML card rendering.

FastAPI is imported lazily inside build_app so importing this module
never fails on a machine without FastAPI installed. The HTML card is a
pure function (render_card_html) so it is testable without a server.
Cards show warnings first, label every line verified or unverified,
show at most a handful of concise lines, and never contain a gate code
value. Synthetic data is labeled in the demo server, not in this module,
because this module serves whatever store it is given.
"""

from html import escape

from .memory import redact_text


def render_card_html(card: dict, stop_id: str) -> str:
    lines = card.get("lines", []) if isinstance(card, dict) else []
    safe_lines = [escape(redact_text(line)) for line in lines]
    items = "".join(f"<li>{line}</li>" for line in safe_lines)
    return (
        "<!DOCTYPE html><html><head><meta name=\"viewport\" "
        "content=\"width=device-width, initial-scale=1\">"
        "<title>Driver card</title></head><body>"
        f"<h1>Stop {escape(stop_id)}</h1>"
        "<p>Synthetic demo data. No gate code values are shown.</p>"
        f"<ul>{items}</ul>"
        "<p>Warnings appear first. Verified and unverified labels are "
        "shown on each line.</p></body></html>")


def build_app(store, agent):
    """Build a FastAPI app bound to the given store and agent."""
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse

    app = FastAPI(title="Driver Intelligence API")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/driver/approach")
    def approach(event: dict):
        result = agent.handle_approach(event)
        if result["action"] == "unauthorized":
            raise HTTPException(status_code=403, detail="driver not assigned")
        if result["action"] == "invalid_event":
            raise HTTPException(status_code=400, detail="invalid event")
        return {"action": result["action"], "card": result["card"],
                "decisions": result["decisions"],
                "trace_steps": len(result["trace"]),
                "llm_calls": result["llm_calls"]}

    @app.post("/driver/feedback")
    def feedback(payload: dict):
        result = agent.record_driver_feedback(payload)
        if not result.get("applied"):
            raise HTTPException(status_code=403, detail=result.get("reason", "rejected"))
        return {"applied": True, "before": result["before"],
                "after": result["after"], "decisions": result["decisions"]}

    @app.get("/driver/card/{stop_id}", response_class=HTMLResponse)
    def card_page(stop_id: str, driver_id: str = ""):
        if driver_id and not store.is_authorized(driver_id, stop_id):
            raise HTTPException(status_code=403, detail="driver not assigned")
        event = {"driver_id": driver_id, "order_id": "demo",
                 "stop_id": stop_id, "distance_miles": 0.5,
                 "eta_minutes": 5, "timestamp": "2026-10-31T12:00:00Z",
                 "event_id": f"card-page:{driver_id}:{stop_id}"}
        result = agent.handle_approach(event)
        if result["action"] in ("unauthorized", "invalid_event"):
            raise HTTPException(status_code=403, detail="driver not assigned")
        return render_card_html(result["card"], stop_id)

    return app
