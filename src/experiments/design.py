"""Experiment design: proactive customer outreach for at-risk deliveries.

Business hypothesis: when the risk model flags an order as likely to arrive
late or earn a low review, sending the customer a proactive, empathetic
message (acknowledging the delay, giving a realistic date, offering help)
raises post-delivery satisfaction relative to saying nothing.

Primary metric: review_score (1-5) on the flagged order.
Secondary metric: low-review rate, defined as review_score <= 2 (binary).
Guardrail metrics (live run only): message opt-out rate, support contact rate.
No uplift is claimed until a live run measures one.

Randomization unit: the customer (customer_unique_id), not the order.
Trade-off, measured on real Olist data (see
evals/experiments/data_exploration.json):
  - For customer-level: the treated entity is the person receiving the
    message. A customer with two flagged orders can never receive both the
    treatment message and silence, which would contaminate the comparison.
    Measured within-customer review correlation is 0.45 (n=2764 pairs), so
    contamination would be substantial, not theoretical.
  - Against customer-level: slightly fewer units than order-level (93,358
    customers vs 96,478 delivered orders here) and the analysis must handle
    customers with several flagged orders (use the first flagged order's
    review as the outcome, pre-registered).
  - Order-level would reach power marginally faster, but at the cost of
    broken independence between units. Customer-level is the valid choice
    for a customer-facing intervention.

Triggering: only customers with at least one flagged order enter the
experiment (a triggered experiment). Assignment is sticky: the first flagged
order fixes the customer's arm for the whole experiment.

Safety: SEND_MESSAGES is False. The pipeline drafts messages and logs
exposures. No message is ever sent to a real customer.
"""

SEND_MESSAGES = False

EXPERIMENT_ID = "outreach-v1"
ARMS = ("control", "treatment")
ALLOCATION = (0.5, 0.5)

ALPHA = 0.05
TARGET_POWER = 0.80
# Minimum detectable effect, in review-score stars. +0.3 moves the late-order
# mean (2.57) meaningfully toward neutral without assuming a miracle.
MDE_STARS = 0.30

# Group-sequential plan: 4 equally spaced looks, O'Brien-Fleming spending.
N_LOOKS = 4

# CUPED gate: only use the covariate adjustment if it cuts variance on
# historical data by at least this fraction.
CUPED_MIN_VARIANCE_REDUCTION = 0.05
