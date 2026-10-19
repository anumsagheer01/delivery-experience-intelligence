"""A/B testing module: customer-outreach experiment.

Design, deterministic assignment, power analysis, statistical analysis
(t-tests, confidence intervals, CUPED with a validation gate, and
group-sequential monitoring with O'Brien-Fleming alpha spending).

Safety: the outreach path only DRAFTS messages. Nothing is ever sent.
See src/agents policy and the SEND_MESSAGES flag in design.py.
"""
