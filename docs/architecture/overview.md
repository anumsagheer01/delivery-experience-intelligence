# Architecture

## System context

A delivery company runs several disconnected systems: order management,
routing, driver photo capture, and customer support. This platform shows how
those signals combine into one decision loop: detect risk, assess evidence,
decide an intervention, audit the decision.

## Component diagram

```
+----------------+     +-----------------+     +-------------------+
|  Olist orders  |     | Amazon routes   |     | OpenStreetMap     |
|  (lifecycle,   |     | (stops, seqs,   |     | (buildings, POIs) |
|   reviews)     |     |  time windows)  |     +-------------------+
+-------+--------+     +--------+--------+              |
        |                       |                       v
        v                       v              +-------------------+
+------------------------------------------------+    | Address classifier|
| Ingestion: validate, normalize, manifest       |    | (BQML logistic    |
| (src/ingestion)                                |    |  regression)      |
+------------------------------------------------+    +--------+----------+
        |                       |                              |
        v                       v                              v
+------------------------------------------------+--------------------------+
| Analytics store: BigQuery raw/staging/marts (local dev: DuckDB)          |
+------------------------------------------------+--------------------------+
        |                       |                              |
        v                       v                              v
+---------------+   +---------------------+   +----------------------------+
| Streaming     |   | Risk models         |   | Vision engine              |
| replay        |   | late / low-review   |   | OpenCV baselines ->        |
| Pub/Sub -> BQ |   | classifiers         |   | AutoML -> Gemini SOP       |
+-------+-------+   +----------+----------+   +-------------+--------------+
        |                      |                            |
        +----------------------+----------------------------+
                               v
                 +----------------------------------+
                 | Intervention agent               |
                 | policy -> tools -> drafts -> audit|
                 +----------------------------------+
                               v
                 +----------------------------------+
                 | Command Center dashboard         |
                 | (Looker Studio + BigQuery views) |
                 +----------------------------------+
```

## Key design decisions (summary; full log in docs/decisions/)

1. Datasets stay independent. No cross-dataset joins are presented as real.
2. ELT: raw data preserved untouched; transforms in SQL.
3. Replay, not simulation: the event stream carries real historical timestamps.
4. Baselines before learned models, everywhere.
5. Cascade for vision: cheap filters first, Gemini only where it adds value.
6. Drafts-only agent: no autonomous external communication.
7. Temporal splits and purchase-time features for risk models (no leakage).
8. Leakage-controlled labels for the address classifier.

## Data flow for the demo

Historical Olist order -> replay producer -> Pub/Sub -> BigQuery events table
-> risk model scores the order -> (controlled scenario) POD photo scored ->
agent applies policy -> draft alert or escalation -> audit record ->
dashboard reflects the decision.
