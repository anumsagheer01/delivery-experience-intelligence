"""Local consumer for simulated DRIVER_APPROACHING_STOP events.

This is the local equivalent of a streaming consumer. No Dataflow job
exists in this repo (only a mention in future-work docs), and none is
claimed here. The consumer reads simulated approach events from a JSONL
file, in the same local-replay pattern as src/streaming, runs the
DriverAgent on each event, and writes one trace record per event to a
JSONL trace file. All events in the demo and evals are synthetic and
are labeled as such in their files. No GPS data and no live location
data are used; distance and ETA are fields supplied in the event.
"""

import json
import os

from ..logging import get_logger

log = get_logger(__name__)


def consume_events(path: str, agent, traces_out: str = "") -> dict:
    """Read JSONL approach events, run the agent, optionally write traces.

    Returns counts: events, cards, duplicates, refused, invalid.
    """
    counts = {"events": 0, "cards": 0, "duplicates": 0,
              "refused": 0, "invalid": 0}
    trace_file = None
    if traces_out:
        os.makedirs(os.path.dirname(traces_out) or ".", exist_ok=True)
        trace_file = open(traces_out, "w", encoding="utf-8")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                counts["events"] += 1
                result = agent.handle_approach(event)
                if result.get("duplicate"):
                    counts["duplicates"] += 1
                elif result["action"] == "unauthorized":
                    counts["refused"] += 1
                elif result["action"] == "invalid_event":
                    counts["invalid"] += 1
                else:
                    counts["cards"] += 1
                if trace_file is not None:
                    trace_file.write(json.dumps({
                        "event": event,
                        "action": result["action"],
                        "card": result.get("card"),
                        "trace": result.get("trace"),
                        "decisions": result.get("decisions"),
                        "audit": result.get("audit"),
                        "llm_calls": result.get("llm_calls"),
                    }) + "\n")
    finally:
        if trace_file is not None:
            trace_file.close()
    log.info("consumed events: %s", counts)
    return counts
