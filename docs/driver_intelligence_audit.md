# Driver Intelligence 2.0: Audit

Date: 2026-10-31. Scope: what already exists, what can be reused, what
needs extending, what genuinely needs creating, what is simulated vs
deployed, and limitations. No em dashes are used in this document.

## Verified repo facts (re-checked against the repo on 2026-10-31)

- Original platform: Olist 99,441 orders, Amazon 6,112 routes, BigQuery
  dataset dei_mart (us-central1), BQML late_delivery_risk holdout
  ROC-AUC 0.6156, low_review_risk 0.5751, local HGB 0.649 and 0.601.
- Pub/Sub cloud throughput 6,235 events per second, 0 loss, 19,770
  events. The older 6,428 figure was local JSONL replay and is
  superseded for the cloud path.
- Agent: 500 orders, 496 no_action plus 4 draft_customer_message,
  500 out of 500 independent policy verification, dry-run only,
  nothing ever sent.
- AutoML Vision: 4,712 images, 99.6 percent accuracy (0.9958) on 471
  held-out test images, batch only, no endpoint.
- A/B test: designed and replay-validated only, about 750 per arm,
  never run live, no uplift claimed.
- Original tests: 31 in tests/. They still pass (see TEST_RESULTS.md).

## What already exists and can be reused

- src/agents/__init__.py: deterministic apply_policy plus
  draft_messages with LLM-optional template fallback. Its policy.md is
  the agent constitution: drafts only, dry-run, idempotency, audit
  everything. The new agent follows the same rules.
- src/streaming/__init__.py: local JSONL replay plus Pub/Sub publish
  modes. The new consumer follows the local replay pattern.
- src/api/__init__.py: FastAPI app with /health,
  /metrics/late-delivery, and /agent/dry-run. FastAPI and uvicorn are
  already in requirements.txt, so the driver card API reuses FastAPI
  and adds no heavy new dependency.
- src/logging get_logger: the new package follows this import pattern.

## What needs extending vs what genuinely needs creating

- Extending: the agent concept (one more agent, same constitution),
  the API pattern (one more router module), and the streaming pattern
  (one more local consumer for a new event type).
- Creating (new, no v1 equivalent): stop memory storage and schema,
  delivery restrictions, deterministic conflict resolution, the
  DRIVER_APPROACHING_STOP pipeline, driver feedback update rules,
  the driver card UI, and the driver intelligence eval suite. None of
  these existed in v1; v1 had order risk and photo evidence, not stop
  level delivery memory.

## Dataflow finding (verified)

No Dataflow code exists in the repo. The only Dataflow mentions are
in docs/decisions/future-work.md (a proposed comparison), in
docs/operations/cost-ledger.md (noting no Dataflow jobs were run), and
in EXECUTION_REPORT.md (future work). This update does NOT claim
Dataflow exists. Approach events are handled by a small local JSONL
consumer (src/driver_intelligence/consumer.py), and that is stated
plainly in the code, the docs, and the demo.

## Gaps carried over from v1 (not fixed by this update)

- Cloud Run deployment: not completed in v1, not completed here.
- Looker Studio connection: not completed in v1, not completed here.
- 300-image human labeling: not completed in v1, not completed here.
- No deployment at a real company, no real messages sent, no live A/B
  test, and no business impact claim are made by this update.

## GCP inspection: read-only position for this update

- Live GCP inspection: NONE performed by this update. This machine
  has no gcloud binary and no GCP configuration directory, so a live
  metadata read could not be verified without installing tooling and
  arranging credentials, which would risk scope creep. Instead, this
  audit relies on repo records: STATUS.md, sql/bigquery_ddl.sql,
  evals/streaming/pubsub_cloud.json, and evals/risk/bqml records.
- GCP writes by this update: ZERO. No dataset, table, topic,
  subscription, deployment, IAM change, billing change, or billable
  job was created, modified, or deleted. All new code and all evals
  run locally. The BigQuery DDL is shipped as a .sql file labeled as
  the production path only, and it is never executed by tests, demos,
  or evals.
- Adapter design for later connection: see
  src/driver_intelligence/adapters.py and INSTALLATION_INSTRUCTIONS.md.
  The local SQLite store and the BigQuery store share the port
  interface; the local JSONL consumer and the Pub/Sub subscriber share
  the agent call. Switchover is a config and construction swap, not a
  rewrite. The BigQuery and Pub/Sub adapter classes are written but
  not connected, and instantiating them makes no network call.

## Simulated vs deployed

- Simulated (local, synthetic, labeled): approach events, stop
  profiles, gate code references, driver feedback, demo stops, and
  all 100 eval scenarios. Distance and ETA are event fields, not GPS.
- Deployed: NOTHING in this update is deployed. The driver card API
  is a local FastAPI app; the demo server binds to 127.0.0.1 only.
- Real (v1, unchanged): the Olist, Amazon, BigQuery, Pub/Sub, AutoML,
  and agent numbers listed at the top of this audit.

## Limitations

- The local store is SQLite or in-memory; it is not a production
  database, has no multi-user concurrency story, and no backup story.
- The LLM summarizer interface is validated by containment and
  keyword checks, not by semantic verification. That is intentionally
  conservative: suspicious output falls back to the deterministic
  card. A production LLM path needs stronger output validation.
- Authorization here means driver assignment in a local table. A
  production system needs real identity, authentication, and audit
  retention, which are documented as not implemented in
  docs/driver_intelligence.md.
- Feedback is synthetic in demos and evals. Real driver feedback
  would need moderation, spam controls, and customer re-verification
  workflows that are out of scope here.
- Latency numbers in evals are local machine numbers, not cloud
  numbers, and must not be quoted as production performance.

## Controls implemented vs needing production infrastructure

Implemented: assignment authorization, gate code value redaction and
never storing code values, expiration of stale access info,
deterministic precedence with safety restrictions always winning,
append-only feedback history, idempotency dedup, prompt injection
rejection, audit records with before and after state, LLM fallback.
Needing production infrastructure: real identity and authentication,
encrypted storage and key management, real customer re-verification,
rate limiting, monitoring and alerting, and data retention controls.
