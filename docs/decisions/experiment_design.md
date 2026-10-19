# Experiment design: proactive customer outreach A/B test

Status: DESIGNED and REPLAY-VALIDATED. Not run live. No uplift claimed.

## Business hypothesis

When the risk model flags an order as likely to arrive late or earn a low
review, sending the customer a proactive, empathetic message (acknowledge the
delay, give a realistic date, offer help) raises post-delivery satisfaction
compared with saying nothing. The experiment exists to test this claim with
real customers before any rollout, because the platform's impact section is
otherwise honest but empty: historical replay, policy correctness, and model
metrics are measured, while business impact is not.

## Design

- Experiment: `outreach-v1`. Arms: control (silence) vs treatment (proactive
  message), 50/50.
- Randomization unit: the customer (`customer_unique_id`), sticky from the
  first flagged order. See the trade-off analysis below.
- Triggering: only customers with at least one flagged order enter. This is a
  triggered experiment; the analysis population is defined before seeing
  outcomes.
- Primary metric: `review_score` (1-5) on the flagged order.
- Secondary metric: low-review rate (`review_score <= 2`, binary).
- Guardrails (live run only): message opt-out rate, support contact rate.
- Outcome rule (pre-registered): one row per customer, using the review of
  their first flagged order.

## Randomization: customer level vs order level

Measured on real Olist data (`evals/experiments/data_exploration.json`):

- 96,478 delivered orders from 93,358 unique customers; only 3.0% of
  customers have more than one order.
- Within-customer review correlation is 0.45 (n=2764 pairs). A customer who
  loved one order tends to love the next.

For customer-level: the treated entity is the person receiving the message.
A customer with two flagged orders can never receive both the treatment
message and silence, which would contaminate the comparison. With a 0.45
within-customer correlation, that contamination would be substantial, not
theoretical. The cost is modest here: 93,358 customers vs 96,478 orders, and
the measured design effect is 1.003, so clustering barely widens confidence
intervals.

Against order-level: it would reach power marginally faster, but it breaks
the independence of units for a customer-facing intervention. In a live
system where customers reorder, the contamination compounds. Customer-level
randomization is the valid choice.

## Sample size (measured, then calibrated)

Baseline among historically late orders: mean 2.57 stars, std 1.66
(n=7,608 eligible customers). Target: detect +0.3 stars at alpha 0.05 with
80% power.

- Textbook two-sample calculation: 482 customers per arm (963 total).
- The catch, found by simulating on the real score distribution: 22.3% of
  late-order reviews are already at the 5-star ceiling, so a hypothetical
  +0.3 shift realizes as +0.233 on average after clipping. Empirical power
  at 482/arm is 0.59, not 0.80.
- Calibrated by simulation (`evals/experiments/sample_size_calibration.json`):
  about 730 customers per arm (1,460 total) reaches 80% power under the
  O'Brien-Fleming plan with the ceiling model.
- Duration: at Olist's observed volume (135 delivered orders/day, 11 late
  orders/day), enrolling 1,460 triggered customers takes roughly 133 days.
  A live deployment at higher volume would be faster; the arithmetic is the
  same.

## Sequential monitoring

Four equally spaced looks (25/50/75/100% of enrollment) under the Lan-DeMets
O'Brien-Fleming alpha-spending function. Pre-registered critical values:
3.92, 2.77, 2.27, 1.95. Reject at look k when |z_k| >= bound_k. This holds
the family-wise type I error at 0.05 across all looks.

Why not just re-run a t-test whenever curiosity strikes: the replay
demonstrates the peeking problem on real data. Under the null, naive
repeated testing rejects 13% of the time; the OBF plan rejects 6.2%,
consistent with the designed 5%. The boundaries are computed in
`src/experiments/power.py` from the canonical joint distribution of
sequential z-statistics, and the null simulation confirms they behave.

## CUPED

Candidate pre-treatment covariates (all known at purchase time, before any
message): order value, freight value, product category, customer state, and
prior review score where a customer has order history.

Measured correlations with review score are weak (|r| <= 0.09, eta-squared
<= 0.01), so the variance-reduction gate (minimum 5%) does not open: the
module computes the adjustment but the design does not use it. Prior review
score correlates at 0.45, which would be an excellent CUPED covariate, but it
exists for only 3% of customers here, so coverage is too thin to matter.
The gate, not optimism, decides. If a live run accumulates richer history,
re-run the gate.

## Validation of the sequential plan (investigation log)

The first replay showed a 6.2% null rejection rate instead of 5%. Asked to
investigate, we found two real problems, not just noise.

1. A bug in our own boundary code. The survival truncation in the
   O'Brien-Fleming recursion was applied after propagating the density
   instead of before, which counted paths that had already crossed and made
   the later bounds too liberal. Under the canonical Brownian-motion model
   the family-wise error was 0.060, provably above 0.05. Fixed by
   truncating first, then propagating. After the fix, 200,000 simulated
   null experiments give 0.0506 with a 95% interval of [0.0496, 0.0516],
   and the per-look rejection increments match the spending function
   almost exactly.

2. A flawed validation design. The first bootstrap kept the hash-fixed arm
   assignment, which freezes each seed's realized difference in the finite
   population of 7,608 customers. At n/N near 20% the resample reproduces
   that nonzero difference and the test rightly rejects it, which inflated
   the measured rate with sample size. Replaced with a permutation null
   (arms exchangeable each seed): 0.056 at n=964 and 0.043 at n=1460, both
   consistent with 0.05 on the real, skewed, discrete outcomes.

The textbook formula was validated independently: on truly normal outcomes
with a true +0.3 effect, 482/arm under the OBF plan gives power 0.79
(95% interval [0.77, 0.81]). The formula is right; the replay shortfall was
entirely the 5-star ceiling, which the calibrated size corrects.

All validation artifacts: `evals/experiments/sequential_validation.json`,
reproducible via `scripts/validate_sequential.py` (fixed seed).

## Theoretical vs calibrated sample size, plainly

The textbook calculation assumes review scores behave like a bell curve
where a +0.3 gain lifts everyone equally: 482 customers per arm. The real
scores are integers from 1 to 5, and 22.3% are already at 5, where no gain
is possible. The +0.3 intention therefore realizes as +0.233 on average,
and the true power at 482/arm is 0.56, not 0.80. The calibrated size comes
from simulating the experiment on the actual score distribution:
about 750 customers per arm (1,500 total) reaches 80% power under the
sequential plan. Realistic need: roughly 1,500 eligible flagged customers.
At Olist's observed volume of about 11 late orders a day, that is around
136 days of enrollment; a live deployment divides that by its own daily
flagged volume.

## What the replay proves and what it does not

Proves: the pipeline is correct end to end. Deterministic assignment splits
arms evenly and stably; the t-tests, CIs, and proportion tests match
reference implementations; the OBF boundaries control the false positive
rate as designed; power lands where the calibrated calculation says it
should. The walk-through in `evals/experiments/replay_results.json` shows a
typical trajectory: wide CIs early, rejection at the final look.

Does not prove: that the message works. The +0.3 shift is simulated,
explicitly labeled, and clipped to the 1-5 range. No real uplift in
satisfaction, reviews, or repeat purchases is claimed or implied. The only
honest measure of impact is a live run, which has not happened.

## Safeguards

- `SEND_MESSAGES = False` in `src/experiments/design.py`. The outreach path
  drafts messages; there is no send path in the module.
- Exposures log to `dei_mart.experiment_exposures` with `message_sent`
  always FALSE.
- Assignment is a pure function of (experiment id, salt, customer id):
  stable across restarts, no database needed to keep arms consistent.

## Reproducibility

- `scripts/explore_experiment_data.py`: measured inputs.
- `scripts/run_power_analysis.py`: measured sample size and OBF bounds.
- `scripts/calibrate_sample_size.py`: simulation-calibrated size.
- `scripts/replay_experiment.py`: pipeline validation (500 null seeds,
  500 effect seeds, seeds fixed).
- `tests/test_experiments.py`: 15 unit tests, all passing.
- BigQuery logging: `sql/experiment_exposures.sql` (staged; create when the
  terminal is free).
