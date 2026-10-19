# Command Center dashboard (Looker Studio)

## What it shows

Four views over the real `dei_mart` dataset in project
`delivery-experience-511901` (us-central1), defined in
`sql/dashboard_views.sql`:

1. **Delivery lateness** (`v_late_by_state`): late-delivery rate by customer
   state, from 96,478 real delivered Olist orders.
2. **Reviews vs lateness** (`v_late_vs_reviews`): average review score split
   by late vs on-time.
3. **Last-mile execution** (`v_zone_revisits`): per-route zone revisits from
   6,112 real Amazon routes (zones entered more than once, extra visits).
4. **Risk operations** (`v_risk_scores`): BQML late-delivery risk score
   distribution on the temporal holdout (sampled ~10%).

A fifth view, `v_agent_audit`, is created after
`scripts/e2e_agent_cloud.py` runs (it needs the `agent_audit` table that
script creates): action mix, escalation rate, audit explorer.

## Setup (reproducible, ~15 minutes)

1. Create the views (Cloud Shell, project already authorized):
   `bq query --nouse_legacy_sql < sql/dashboard_views.sql`
   (paste the file into the BigQuery console works too).
2. In Looker Studio, create a blank report and add a BigQuery data source.
3. Connect each view (project `delivery-experience-511901`, dataset
   `dei_mart`, table = view name).
4. Suggested charts:
   - lateness: scorecard (overall late rate) + bar (late rate by state,
     `v_late_by_state`) + table (`v_late_vs_reviews`)
   - last-mile: bar (routes by zones_revisited) + table (top routes by
     extra_zone_visits, `v_zone_revisits`)
   - risk: histogram (risk_score, `v_risk_scores`)
   - interventions: bar (action mix) + table (audit records, newest first,
     `v_agent_audit` once created)
5. Data provenance: every chart subtitle names its source view. Populations
   are never mixed: Olist charts say Olist, Amazon charts say Amazon.

## Fallback

If Looker Studio cannot be connected from your environment, the same views
can be rendered with the matplotlib script `scripts/render_charts.py`
(output PNGs under `dashboard/preview/`).
