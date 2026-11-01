"""Demo: Driver Intelligence Agent, full loop, local only, no GCP.

SYNTHETIC DATA: every stop, driver, gate code reference, instruction,
and feedback item in this demo is synthetic. Nothing here came from a
real customer, a real driver, or a real delivery.

Run from the repo root:
  python scripts/demo_driver_intelligence.py
  python scripts/demo_driver_intelligence.py --traces-out \
      evals/driver_intelligence/traces/demo_traces.jsonl

What it shows, in order:
  1. Apartment delivery: placement, access, contact, leave restriction.
  2. Conflicting instructions: old verified historical "leave at front
     door" vs newer verified customer "use parcel locker"; verified
     wins, with the reason shown in the trace.
  3. Incorrect gate code: card shows verified access, driver reports
     it failed, memory is invalidated, the next approach warns that
     access requires verification.
  Plus a fallback check: the same card with an unavailable LLM, where
  the trace shows the deterministic fallback decision.
Nothing is sent to anyone. Cards are drafts for display only.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.driver_intelligence.agent import DriverAgent  # noqa: E402
from src.driver_intelligence.memory import (  # noqa: E402
    Observation,
    StopMemoryStore,
    StopProfile,
)
from src.driver_intelligence.feedback import process_feedback  # noqa: E402


def show(title, result):
    print(f"\n=== {title} ===")
    print(f"Action: {result['action']}")
    print("Tool trace:")
    for step in result["trace"]:
        print(f"  {step['step']}. {step['tool']}: {step['result']}")
        if step.get("decision"):
            print(f"     decision: {step['decision']} | rule: {step['rule']}")
    card = result.get("card")
    if card:
        print("Driver card:")
        for line in card["lines"]:
            print(f"  - {line}")
        print(f"  LLM calls: {card['llm_calls']}, "
              f"fallback used: {card['fallback_used']}, "
              f"reason: {card['fallback_reason']}")
    print(f"Audit: {result['audit']}")


def seed(store):
    store.assign_driver("driver_demo_1", "stop_apt_101")
    store.assign_driver("driver_demo_1", "stop_locker_202")
    store.assign_driver("driver_demo_2", "stop_gate_303")
    store.upsert_profile(StopProfile(
        stop_id="stop_apt_101", address_id="addr_synth_101",
        building_type="apartment",
        preferred_entrance="Use side entrance by the mailroom",
        preferred_placement="Leave at apartment door, unit 4B",
        contact_preference="Text on arrival, do not knock",
        access_instructions="Side entrance; gate code on file (reference only)",
        gate_code_ref="ref_gate_synth_101", gate_verification_status="verified",
        leave_unattended_restriction=True,
        leave_restriction_reason="Building policy: do not leave unattended in lobby.",
        instruction_source="verified_customer", verification_status="verified",
        confidence=0.9))
    store.upsert_profile(StopProfile(
        stop_id="stop_locker_202", address_id="addr_synth_202",
        building_type="apartment",
        preferred_entrance="Use main lobby entrance",
        preferred_placement="Use parcel locker in the lobby",
        contact_preference="Text on arrival",
        access_instructions="Lobby access; gate code on file (reference only)",
        gate_code_ref="ref_gate_synth_202", gate_verification_status="verified",
        instruction_source="verified_customer", verification_status="verified",
        confidence=0.9))
    store.add_observation(Observation(
        stop_id="stop_locker_202", kind="placement",
        text="Leave at front door", source_type="verified_historical",
        verification_status="verified", created_at="2026-01-05T10:00:00+00:00"))
    store.upsert_profile(StopProfile(
        stop_id="stop_gate_303", address_id="addr_synth_303",
        building_type="house",
        preferred_entrance="Use front gate",
        preferred_placement="Leave at front porch",
        contact_preference="Text on arrival",
        access_instructions="Front gate; gate code on file (reference only)",
        gate_code_ref="ref_gate_synth_303", gate_verification_status="verified",
        instruction_source="verified_customer", verification_status="verified",
        confidence=0.9))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces-out", default=
                        "evals/driver_intelligence/traces/demo_traces.jsonl")
    args = parser.parse_args()
    print("SYNTHETIC DEMO DATA ONLY. No GCP, no network, nothing sent.")
    store = StopMemoryStore()
    seed(store)
    agent = DriverAgent(store, llm_summarizer=None)
    traces = []

    def run(title, event):
        result = agent.handle_approach(event)
        show(title, result)
        traces.append({"event": event, "action": result["action"],
                       "card": result.get("card"), "trace": result["trace"],
                       "decisions": result["decisions"],
                       "audit": result["audit"],
                       "llm_calls": result["llm_calls"]})
        return result

    run("Scenario 1: apartment delivery", {
        "event_id": "evt_demo_1", "event_type": "DRIVER_APPROACHING_STOP",
        "driver_id": "driver_demo_1", "order_id": "order_synth_1",
        "stop_id": "stop_apt_101", "distance_miles": 0.4, "eta_minutes": 4,
        "timestamp": "2026-10-31T12:00:00Z"})
    run("Scenario 2: conflicting instructions", {
        "event_id": "evt_demo_2", "event_type": "DRIVER_APPROACHING_STOP",
        "driver_id": "driver_demo_1", "order_id": "order_synth_2",
        "stop_id": "stop_locker_202", "distance_miles": 0.3, "eta_minutes": 3,
        "timestamp": "2026-10-31T12:10:00Z"})
    run("Scenario 3a: gate code shown verified", {
        "event_id": "evt_demo_3a", "event_type": "DRIVER_APPROACHING_STOP",
        "driver_id": "driver_demo_2", "order_id": "order_synth_3",
        "stop_id": "stop_gate_303", "distance_miles": 0.5, "eta_minutes": 5,
        "timestamp": "2026-10-31T12:20:00Z"})
    fb = process_feedback(store, {
        "driver_id": "driver_demo_2", "stop_id": "stop_gate_303",
        "feedback_type": "gate_code_incorrect",
        "note": "Gate code on file did not open the gate (synthetic feedback)."})
    print("\n=== Scenario 3b: driver feedback ===")
    print(f"Applied: {fb['applied']}, reason: {fb['reason']}")
    print(f"Before gate status: {fb['before']['gate_verification_status']}")
    print(f"After gate status: {fb['after']['gate_verification_status']}")
    print("Feedback trace:")
    for step in fb["trace"]:
        print(f"  {step['step']}. {step['tool']}: {step['result']}")
        if step.get("decision"):
            print(f"     decision: {step['decision']} | rule: {step['rule']}")
    traces.append({"event": {"feedback": True, "stop_id": "stop_gate_303"},
                   "action": "feedback", "card": None, "trace": fb["trace"],
                   "decisions": fb["decisions"], "audit": None,
                   "llm_calls": 0,
                   "before": fb["before"], "after": fb["after"]})
    run("Scenario 3c: next approach warns access requires verification", {
        "event_id": "evt_demo_3c", "event_type": "DRIVER_APPROACHING_STOP",
        "driver_id": "driver_demo_2", "order_id": "order_synth_3b",
        "stop_id": "stop_gate_303", "distance_miles": 0.5, "eta_minutes": 5,
        "timestamp": "2026-10-31T12:30:00Z"})
    failing_agent = DriverAgent(store, llm_summarizer=_failing_llm)
    failing_agent._seen_events = {}
    result = failing_agent.handle_approach({
        "event_id": "evt_demo_fallback", "event_type": "DRIVER_APPROACHING_STOP",
        "driver_id": "driver_demo_1", "order_id": "order_synth_fb",
        "stop_id": "stop_apt_101", "distance_miles": 0.4, "eta_minutes": 4,
        "timestamp": "2026-10-31T12:40:00Z"})
    show("Fallback check: LLM unavailable, deterministic card used", result)
    traces.append({"event": {"fallback_check": True},
                   "action": result["action"], "card": result.get("card"),
                   "trace": result["trace"], "decisions": result["decisions"],
                   "audit": result["audit"], "llm_calls": result["llm_calls"]})
    if args.traces_out:
        os.makedirs(os.path.dirname(args.traces_out) or ".", exist_ok=True)
        with open(args.traces_out, "w", encoding="utf-8") as f:
            for record in traces:
                f.write(json.dumps(record) + "\n")
        print(f"\nTraces written to: {args.traces_out} ({len(traces)} records)")
    print("\nDemo complete. Full loop shown: history -> memory -> alert -> "
          "feedback -> updated memory -> improved next alert.")


def _failing_llm(lines):
    raise RuntimeError("simulated LLM outage")


if __name__ == "__main__":
    main()
