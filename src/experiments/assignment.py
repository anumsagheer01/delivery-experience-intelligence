"""Deterministic experiment assignment.

Assignment is a pure function of (experiment_id, salt, unit_id): the same
customer always lands in the same arm, across processes, machines, and
restarts, with no lookup table required. Exposures are still logged to
BigQuery for analysis; the hash only decides the arm.
"""
import hashlib

from .design import ALLOCATION, ARMS, EXPERIMENT_ID


def _unit_hash(experiment_id: str, salt: str, unit_id: str) -> float:
    digest = hashlib.sha256(
        f"{experiment_id}:{salt}:{unit_id}".encode("utf-8")
    ).hexdigest()
    return int(digest, 16) / 2**256


def assign(unit_id: str, salt: str = "v1",
           experiment_id: str = EXPERIMENT_ID,
           arms=ARMS, allocation=ALLOCATION) -> str:
    """Return the arm for a unit. Deterministic and stable."""
    if abs(sum(allocation) - 1.0) > 1e-9:
        raise ValueError("allocation weights must sum to 1")
    u = _unit_hash(experiment_id, salt, str(unit_id))
    cumulative = 0.0
    for arm, weight in zip(arms, allocation):
        cumulative += weight
        if u < cumulative:
            return arm
    return arms[-1]


def draft_outreach_message(customer_name: str, order_id: str,
                           risk_reason: str) -> dict:
    """Draft (never send) the proactive outreach message.

    Returns the message payload that WOULD be sent. Sending is disabled by
    design: there is no send path in this module.
    """
    return {
        "to_customer": customer_name,
        "order_id": order_id,
        "channel": "email",
        "subject": "An update on your delivery",
        "body": (
            f"Hi {customer_name}, we noticed your order {order_id} may arrive "
            f"later than expected ({risk_reason}). We are sorry for the "
            "inconvenience and we are keeping an eye on it. If you need "
            "anything, just reply to this message and we will help."
        ),
        "sent": False,
    }
