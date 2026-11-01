# AI Agent Intervention Policy

This document explains when the AI agent should respond to delivery issues, what actions it can take, and the safety rules it must follow.

## 1. When Does the Agent Take Action?

The agent reviews a delivery when any of these conditions occur:

1. **Package issue:** The delivery photo suggests the package is missing, placed incorrectly, or left somewhere unsafe.
2. **Late-delivery risk:** The ML model predicts a delay above the configured risk threshold.
3. **Poor delivery experience:** An order arrives late and receives a review score of 2 stars or lower, or its delivery time is more than twice the state median.
4. **Repeated issues:** A driver receives two consecutive poor delivery-photo flags on the same route.

## 2. What Can the Agent Do?

| Action | Description |
|---|---|
| `draft_driver_alert` | Prepare feedback for a driver about a delivery issue. |
| `draft_customer_message` | Draft a message informing a customer about a possible delay. |
| `no_action` | Take no action when there is no significant issue. |
| `escalate` | Flag the situation for human review. |

The agent only prepares recommendations and drafts. It does not independently send messages.

## 3. Safety Rules

The agent must follow these rules:

1. **Human approval:** Messages remain drafts until approved by a person. Live actions require explicit permission.
2. **No duplicate actions:** The same order and event type should not trigger repeated interventions.
3. **Record decisions:** Log each decision, including the reason and confidence level.
4. **Limit tool usage:** Allow a maximum of four tool rounds per event. If the output cannot be understood, escalate.
5. **Use verified information:** Base decisions on tool results without inventing details.
6. **Escalate sensitive cases:** Issues involving driver pay, safety, account status, repeated problems, complaints, or low model confidence (below 0.6) require human review.

## 4. Default Behavior

When there is not enough information to make a reliable decision, the agent should escalate the case rather than make assumptions.

**Goal:** Identify delivery problems early while keeping decisions transparent, controlled, and subject to human oversight.
