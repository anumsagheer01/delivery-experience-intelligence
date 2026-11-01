### A/B Testing & Experimentation

Designed a customer-level A/B test to evaluate whether proactive delivery-delay notifications could improve customer satisfaction.

- **Experiment:** 50/50 treatment-control split, randomized by customer to avoid contamination.
- **Data:** Analyzed 7,608 eligible customers with an average review score of 2.57 stars.
- **Statistical power:** Used simulations to calibrate the sample size to approximately 750 customers per group for 80% power.
- **Sequential testing:** Designed four monitoring checkpoints using O'Brien-Fleming boundaries; validated a 5.06% false-positive rate across 200,000 null simulations.
- **Variance reduction:** Evaluated CUPED but excluded it because available covariates offered limited benefit.

**Status:** Experiment designed and simulation-validated, not run live. No actual customer satisfaction improvement is claimed.

**Evidence:** [Experiment evaluation results](evals/experiments/)
