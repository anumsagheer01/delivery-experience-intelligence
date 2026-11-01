# Driver Intelligence Agent (Delivery Experience Intelligence 2.0)

Synthetic data notice: demos and evals use synthetic stops, drivers,
gate code references, instructions, and feedback. Nothing in the demo
or eval data came from a real customer or driver. No messages are ever
sent by this code; driver cards are drafts for display only.

## What it does (three capabilities, nothing more)

1. Delivery Stop Memory: a per-stop memory of entrance, placement,
   contact preference, access instructions, gate code reference only
   (never the code value), leave unattended restrictions, known access
   problems, source, verification status, confidence, and expiry.
2. Proactive Driver Alerts: on a DRIVER_APPROACHING_STOP event, the
   agent runs a real tool calling loop and returns a concise driver
   card, warnings first, with verified and unverified labels.
3. Driver Feedback and Memory Updates: driver reports are validated,
   authorized, appended to history, and applied by deterministic rules
   that flag and downgrade but never silently replace verified
   customer instructions.

Out of scope, by design: road-width checks, truck routing, live GPS,
new computer vision models, multi-agent architectures, new model
training, and always-on services.

## How it works: the tool loop (the trace is the proof)

For each approach event, in order:

1. validate_event: required fields, non-negative distance and ETA.
2. check_authorization: the driver must be assigned to the stop, or
   the agent refuses and discloses no memory.
3. get_stop_memory: profile plus append-only observations, with stale
   profiles expired first.
4. check_delivery_restrictions: leave restrictions, access problems,
   invalid gate codes, and expired access info.
5. resolve_instruction_conflicts: deterministic priority, lowest rank
   wins: (1) verified customer instructions, (2) policies and
   restrictions, (3) verified operational updates, (4) verified
   historical observations, (5) unverified historical observations,
   (6) unverified driver reports. Safety restrictions always win,
   regardless of conflicts. Every resolution records which instruction
   won and why.
6. decide: warn vs proceed, show gate status only vs suppress the
   code value (always suppress the value), stale vs fresh.
7. generate_driver_card: deterministic card first, then LLM
   summarization last, only if configured. The LLM receives only the
   deterministic card lines and must return a condensation of them;
   on failure, injection markers, invented instructions, or gate code
   phrasing, the deterministic fallback card is used. With no LLM
   configured, the fallback card is used and LLM calls per event are 0.
8. audit: the decision, reasons, rules cited, card lines, and LLM
   call count are recorded. Idempotency key is (driver_id, stop_id,
   event_id): duplicates reuse the prior card and add no new audit
   record, and are counted as handled, not errors.

Feedback loop: validate type, check authorization, append an
unverified observation, apply the update rule, record before and
after state. gate_code_incorrect moves a verified gate code to
invalid pending verification; it is never shown as confirmed again
until explicit re-verification. Other feedback flags the instruction
for review and downgrades confidence, but keeps verified customer
text intact.

## Architecture notes

- New package: src/driver_intelligence/, following repo conventions
  (module docstring, get_logger, plain functions, dataclasses).
- memory.py: StopMemoryStore (SQLite, in-memory by default) with the
  same fields as sql/driver_intelligence_schema.sql.
- agent.py: DriverAgent, the single agent and its tool loop.
- feedback.py: process_feedback, the deterministic update rules.
- consumer.py: local JSONL consumer for simulated approach events.
  No Dataflow code exists in this repo and none is claimed; this is
  the local equivalent, stated plainly.
- card_api.py: mountable FastAPI router (build_app) plus pure HTML
  rendering (render_card_html). FastAPI is imported lazily so the
  module imports without FastAPI installed.
- adapters.py: port interface plus BigQuery and Pub/Sub adapters
  that are written but NOT connected. See the switchover steps in
  INSTALLATION_INSTRUCTIONS.md. No test, demo, or eval instantiates
  them for execution; a test checks only that instantiation makes no
  connection.
- No GCP calls, no network calls, and no billable resources are used
  by the demo, tests, or evals. Incremental cloud cost is $0.

## How to run

From the repo root, using the project virtual environment:

```bash
python -m pytest tests/ -q
python scripts/demo_driver_intelligence.py
python scripts/evaluate_driver_intelligence.py
```

Card API server (local only, synthetic demo data):

```bash
python scripts/serve_driver_card.py
# then open:
# http://127.0.0.1:8000/driver/card/stop_apt_101?driver_id=driver_demo_1
```

API endpoints (from card_api.build_app):

- POST /driver/approach: process an approach event, return the card,
  decisions, trace step count, and LLM call count.
- POST /driver/feedback: submit feedback, return before and after
  state plus decisions.
- GET /driver/card/{stop_id}?driver_id=...: minimal mobile-readable
  HTML card page, warnings first, verified and unverified labeled,
  no gate code values.

## Security: implemented vs production infrastructure needed

Implemented: assignment authorization, gate code value redaction on
ingest and in logs and audit records, storing references only,
expiration of stale access info, deterministic restrictions that
always win, append-only history, idempotency, prompt injection
rejection, and full decision traces.

Still needed in production (not implemented here): real identity and
authentication, encrypted storage and key management, customer
re-verification workflows, rate limiting, monitoring, alerting, and
data retention and deletion controls. Do not present this demo as
production-grade security.

## Limitations

- Local SQLite is not a production database; no concurrency, backup,
  or multi-user story is claimed.
- LLM output validation is containment and keyword based, not
  semantic. Suspicious output falls back safely, but a production
  path needs stronger validation.
- Eval latencies are local machine numbers, not production numbers.
- The 500 out of 500 v1 policy match means the deterministic policy
  reproduced itself on those 500 cases; it does not mean 100 percent
  AI understanding, and this update makes no such claim.
- No deployment at a real company, no real messages sent, no live A/B
  test, and no business impact (such as fewer failed deliveries) is
  claimed.
