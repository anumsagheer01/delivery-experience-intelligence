# Driver Intelligence Demo: commands and expected outputs

SYNTHETIC DATA ONLY: every stop, driver, gate code reference,
instruction, and feedback item below is synthetic. No real customer,
driver, or gate code data is used. No messages are sent.

## Commands (run from the repo root)

```bash
python -m pytest tests/ -q
python scripts/demo_driver_intelligence.py
python scripts/demo_driver_intelligence.py --traces-out evals/driver_intelligence/traces/demo_traces.jsonl
python scripts/evaluate_driver_intelligence.py
python scripts/serve_driver_card.py
```

The card server binds to 127.0.0.1 only. Open:
http://127.0.0.1:8000/driver/card/stop_apt_101?driver_id=driver_demo_1

## Expected demo output (real output, logger lines removed)

Logger lines (timestamps and INFO lines) are removed for readability;
audit decided_at timestamps will differ on each run. Everything else
below is copied from a real run on 2026-10-31 local time. The demo
also writes 6 trace records to
evals/driver_intelligence/traces/demo_traces.jsonl.

```text
SYNTHETIC DEMO DATA ONLY. No GCP, no network, nothing sent.

=== Scenario 1: apartment delivery ===
Action: warn
Tool trace:
  1. validate_event: event valid
     decision: proceed | rule: VALIDATION_RULE: required fields and non-negative distance and ETA
  2. check_authorization: authorized
     decision: proceed | rule: AUTHORIZATION_RULE: driver must be assigned to the stop
  3. get_stop_memory: profile found=True; observations=0; verification=verified
  4. check_delivery_restrictions: 1 restrictions found
     decision: warn | rule: SAFETY_RULE: restrictions always win
  5. resolve_instruction_conflicts: entrance=Use side entrance by the mailroom (verified_customer); placement=Leave at apartment door, unit 4B (verified_customer)
     decision: apply priority ranking; restrictions override winners | rule: PRIORITY_RULE: verified customer (1) > policy (2) > verified operational (3) > verified historical (4) > unverified historical (5) > unverified driver (6); SAFETY_RULE: restrictions always win
  6. weigh_alternative: kind=leave_unattended: restriction kept regardless of conflicts: Building policy: do not leave unattended in lobby.
     decision: winner kept, loser suppressed | rule: PRIORITY_RULE
  7. decide_alert_level: warn
     decision: warn | rule: ALERT_RULE: any restriction, stale, or missing memory produces a warning card
  8. decide_gate_code_display: show status only, never the code value
     decision: suppress gate code value; show status only | rule: SECURITY_RULE: gate code values are never shown, logged, or audited
  9. generate_driver_card: llm_used=False; fallback_used=True; lines=7; reason=no LLM configured; deterministic fallback used
     decision: use deterministic fallback card | rule: LLM_RULE: LLM summarizes verified card lines only, after deterministic decisions; fallback on failure
Driver card:
  - WARNING: Building policy: do not leave unattended in lobby.
  - Entrance (verified): Use side entrance by the mailroom
  - Placement (verified): Leave at apartment door, unit 4B
  - Contact (verified): Text on arrival, do not knock
  - Gate code: on file and verified (code value never shown).
  - Building: apartment
  - ETA: 4 minutes, 0.4 miles away.
  LLM calls: 0, fallback used: True, reason: no LLM configured; deterministic fallback used
Audit: {'event_id': 'evt_demo_1', 'driver_id': 'driver_demo_1', 'order_id': 'order_synth_1', 'stop_id': 'stop_apt_101', 'action': 'warn', 'message': 'card generated; warnings=1', 'card_lines': ['WARNING: Building policy: do not leave unattended in lobby.', 'Entrance (verified): Use side entrance by the mailroom', 'Placement (verified): Leave at apartment door, unit 4B', 'Contact (verified): Text on arrival, do not knock', 'Gate code: on file and verified (code value never shown).', 'Building: apartment', 'ETA: 4 minutes, 0.4 miles away.'], 'llm_calls': 0, 'duplicate': False, 'decided_at': '2026-11-01T01:30:57.859953+00:00'}

=== Scenario 2: conflicting instructions ===
Action: proceed
Tool trace:
  1. validate_event: event valid
     decision: proceed | rule: VALIDATION_RULE: required fields and non-negative distance and ETA
  2. check_authorization: authorized
     decision: proceed | rule: AUTHORIZATION_RULE: driver must be assigned to the stop
  3. get_stop_memory: profile found=True; observations=1; verification=verified
  4. check_delivery_restrictions: 0 restrictions found
     decision: no restriction warning | rule: SAFETY_RULE: restrictions always win
  5. resolve_instruction_conflicts: entrance=Use main lobby entrance (verified_customer); placement=Use parcel locker in the lobby (verified_customer)
     decision: apply priority ranking; restrictions override winners | rule: PRIORITY_RULE: verified customer (1) > policy (2) > verified operational (3) > verified historical (4) > unverified historical (5) > unverified driver (6); SAFETY_RULE: restrictions always win
  6. weigh_alternative: kind=placement: winner 'Use parcel locker in the lobby' (verified_customer) beat loser 'Leave at front door' (verified_historical); PRIORITY_RULE: verified customer instructions (rank 1) beat verified historical observations (rank 4)
     decision: winner kept, loser suppressed | rule: PRIORITY_RULE
  7. decide_alert_level: proceed
     decision: proceed | rule: ALERT_RULE: any restriction, stale, or missing memory produces a warning card
  8. decide_gate_code_display: show status only, never the code value
     decision: suppress gate code value; show status only | rule: SECURITY_RULE: gate code values are never shown, logged, or audited
  9. generate_driver_card: llm_used=False; fallback_used=True; lines=6; reason=no LLM configured; deterministic fallback used
     decision: use deterministic fallback card | rule: LLM_RULE: LLM summarizes verified card lines only, after deterministic decisions; fallback on failure
Driver card:
  - Entrance (verified): Use main lobby entrance
  - Placement (verified): Use parcel locker in the lobby
  - Contact (verified): Text on arrival
  - Gate code: on file and verified (code value never shown).
  - Building: apartment
  - ETA: 3 minutes, 0.3 miles away.
  LLM calls: 0, fallback used: True, reason: no LLM configured; deterministic fallback used
Audit: {'event_id': 'evt_demo_2', 'driver_id': 'driver_demo_1', 'order_id': 'order_synth_2', 'stop_id': 'stop_locker_202', 'action': 'proceed', 'message': 'card generated; warnings=0', 'card_lines': ['Entrance (verified): Use main lobby entrance', 'Placement (verified): Use parcel locker in the lobby', 'Contact (verified): Text on arrival', 'Gate code: on file and verified (code value never shown).', 'Building: apartment', 'ETA: 3 minutes, 0.3 miles away.'], 'llm_calls': 0, 'duplicate': False, 'decided_at': '2026-11-01T01:30:57.860421+00:00'}

=== Scenario 3a: gate code shown verified ===
Action: proceed
Tool trace:
  1. validate_event: event valid
     decision: proceed | rule: VALIDATION_RULE: required fields and non-negative distance and ETA
  2. check_authorization: authorized
     decision: proceed | rule: AUTHORIZATION_RULE: driver must be assigned to the stop
  3. get_stop_memory: profile found=True; observations=0; verification=verified
  4. check_delivery_restrictions: 0 restrictions found
     decision: no restriction warning | rule: SAFETY_RULE: restrictions always win
  5. resolve_instruction_conflicts: entrance=Use front gate (verified_customer); placement=Leave at front porch (verified_customer)
     decision: apply priority ranking; restrictions override winners | rule: PRIORITY_RULE: verified customer (1) > policy (2) > verified operational (3) > verified historical (4) > unverified historical (5) > unverified driver (6); SAFETY_RULE: restrictions always win
  6. decide_alert_level: proceed
     decision: proceed | rule: ALERT_RULE: any restriction, stale, or missing memory produces a warning card
  7. decide_gate_code_display: show status only, never the code value
     decision: suppress gate code value; show status only | rule: SECURITY_RULE: gate code values are never shown, logged, or audited
  8. generate_driver_card: llm_used=False; fallback_used=True; lines=6; reason=no LLM configured; deterministic fallback used
     decision: use deterministic fallback card | rule: LLM_RULE: LLM summarizes verified card lines only, after deterministic decisions; fallback on failure
Driver card:
  - Entrance (verified): Use front gate
  - Placement (verified): Leave at front porch
  - Contact (verified): Text on arrival
  - Gate code: on file and verified (code value never shown).
  - Building: house
  - ETA: 5 minutes, 0.5 miles away.
  LLM calls: 0, fallback used: True, reason: no LLM configured; deterministic fallback used
Audit: {'event_id': 'evt_demo_3a', 'driver_id': 'driver_demo_2', 'order_id': 'order_synth_3', 'stop_id': 'stop_gate_303', 'action': 'proceed', 'message': 'card generated; warnings=0', 'card_lines': ['Entrance (verified): Use front gate', 'Placement (verified): Leave at front porch', 'Contact (verified): Text on arrival', 'Gate code: on file and verified (code value never shown).', 'Building: house', 'ETA: 5 minutes, 0.5 miles away.'], 'llm_calls': 0, 'duplicate': False, 'decided_at': '2026-11-01T01:30:57.860769+00:00'}

=== Scenario 3b: driver feedback ===
Applied: True, reason: gate code status verified -> invalid pending verification; re-verification required
Before gate status: verified
After gate status: invalid
Feedback trace:
  1. check_authorization: authorized
     decision: proceed | rule: AUTHORIZATION_RULE: driver must be assigned to the stop
  2. get_stop_memory: before verification=verified; gate=verified
  3. record_observation: append-only observation recorded as unverified_driver
     decision: append history, do not overwrite verified instructions | rule: HISTORY_RULE: observations are append-only; verified customer instructions are never overwritten by driver claims
  4. apply_update_rule: gate code status verified -> invalid pending verification; re-verification required
     decision: invalidate gate code, keep customer instruction text | rule: GATE_RULE: a reported-bad gate code loses verified status and is never shown as confirmed again
  5. record_audit: after verification=verified; gate=invalid
     decision: feedback applied as flag/downgrade | rule: AUDIT_RULE: every feedback decision is recorded with before and after state

=== Scenario 3c: next approach warns access requires verification ===
Action: warn
Tool trace:
  1. validate_event: event valid
     decision: proceed | rule: VALIDATION_RULE: required fields and non-negative distance and ETA
  2. check_authorization: authorized
     decision: proceed | rule: AUTHORIZATION_RULE: driver must be assigned to the stop
  3. get_stop_memory: profile found=True; observations=1; verification=verified
  4. check_delivery_restrictions: 2 restrictions found
     decision: warn | rule: SAFETY_RULE: restrictions always win
  5. resolve_instruction_conflicts: entrance=Use front gate (verified_customer); gate_code_incorrect=Gate code on file did not open the gate (synthetic feedback). (unverified_driver); placement=Leave at front porch (verified_customer)
     decision: apply priority ranking; restrictions override winners | rule: PRIORITY_RULE: verified customer (1) > policy (2) > verified operational (3) > verified historical (4) > unverified historical (5) > unverified driver (6); SAFETY_RULE: restrictions always win
  6. weigh_alternative: kind=access_problem: restriction kept regardless of conflicts: Driver reported gate code incorrect (synthetic feedback).
     decision: winner kept, loser suppressed | rule: PRIORITY_RULE
  7. weigh_alternative: kind=gate_code: restriction kept regardless of conflicts: Gate code is invalid pending verification. Do not rely on the stored access code.
     decision: winner kept, loser suppressed | rule: PRIORITY_RULE
  8. decide_alert_level: warn
     decision: warn | rule: ALERT_RULE: any restriction, stale, or missing memory produces a warning card
  9. decide_gate_code_display: show status only, never the code value
     decision: suppress gate code value; show status only | rule: SECURITY_RULE: gate code values are never shown, logged, or audited
  10. generate_driver_card: llm_used=False; fallback_used=True; lines=8; reason=no LLM configured; deterministic fallback used
     decision: use deterministic fallback card | rule: LLM_RULE: LLM summarizes verified card lines only, after deterministic decisions; fallback on failure
Driver card:
  - WARNING: Driver reported gate code incorrect (synthetic feedback).
  - WARNING: Gate code is invalid pending verification. Do not rely on the stored access code.
  - Entrance (verified): Use front gate
  - Placement (verified): Leave at front porch
  - Contact (verified): Text on arrival
  - Gate code: requires verification (status: invalid). Do not rely on it.
  - Building: house
  - ETA: 5 minutes, 0.5 miles away.
  LLM calls: 0, fallback used: True, reason: no LLM configured; deterministic fallback used
Audit: {'event_id': 'evt_demo_3c', 'driver_id': 'driver_demo_2', 'order_id': 'order_synth_3b', 'stop_id': 'stop_gate_303', 'action': 'warn', 'message': 'card generated; warnings=2', 'card_lines': ['WARNING: Driver reported gate code incorrect (synthetic feedback).', 'WARNING: Gate code is invalid pending verification. Do not rely on the stored access code.', 'Entrance (verified): Use front gate', 'Placement (verified): Leave at front porch', 'Contact (verified): Text on arrival', 'Gate code: requires verification (status: invalid). Do not rely on it.', 'Building: house', 'ETA: 5 minutes, 0.5 miles away.'], 'llm_calls': 0, 'duplicate': False, 'decided_at': '2026-11-01T01:30:57.861529+00:00'}

=== Fallback check: LLM unavailable, deterministic card used ===
Action: warn
Tool trace:
  1. validate_event: event valid
     decision: proceed | rule: VALIDATION_RULE: required fields and non-negative distance and ETA
  2. check_authorization: authorized
     decision: proceed | rule: AUTHORIZATION_RULE: driver must be assigned to the stop
  3. get_stop_memory: profile found=True; observations=0; verification=verified
  4. check_delivery_restrictions: 1 restrictions found
     decision: warn | rule: SAFETY_RULE: restrictions always win
  5. resolve_instruction_conflicts: entrance=Use side entrance by the mailroom (verified_customer); placement=Leave at apartment door, unit 4B (verified_customer)
     decision: apply priority ranking; restrictions override winners | rule: PRIORITY_RULE: verified customer (1) > policy (2) > verified operational (3) > verified historical (4) > unverified historical (5) > unverified driver (6); SAFETY_RULE: restrictions always win
  6. weigh_alternative: kind=leave_unattended: restriction kept regardless of conflicts: Building policy: do not leave unattended in lobby.
     decision: winner kept, loser suppressed | rule: PRIORITY_RULE
  7. decide_alert_level: warn
     decision: warn | rule: ALERT_RULE: any restriction, stale, or missing memory produces a warning card
  8. decide_gate_code_display: show status only, never the code value
     decision: suppress gate code value; show status only | rule: SECURITY_RULE: gate code values are never shown, logged, or audited
  9. generate_driver_card: llm_used=False; fallback_used=True; lines=7; reason=LLM unavailable (simulated LLM outage); fallback used
     decision: use deterministic fallback card | rule: LLM_RULE: LLM summarizes verified card lines only, after deterministic decisions; fallback on failure
Driver card:
  - WARNING: Building policy: do not leave unattended in lobby.
  - Entrance (verified): Use side entrance by the mailroom
  - Placement (verified): Leave at apartment door, unit 4B
  - Contact (verified): Text on arrival, do not knock
  - Gate code: on file and verified (code value never shown).
  - Building: apartment
  - ETA: 4 minutes, 0.4 miles away.
  LLM calls: 0, fallback used: True, reason: LLM unavailable (simulated LLM outage); fallback used
Audit: {'event_id': 'evt_demo_fallback', 'driver_id': 'driver_demo_1', 'order_id': 'order_synth_fb', 'stop_id': 'stop_apt_101', 'action': 'warn', 'message': 'card generated; warnings=1', 'card_lines': ['WARNING: Building policy: do not leave unattended in lobby.', 'Entrance (verified): Use side entrance by the mailroom', 'Placement (verified): Leave at apartment door, unit 4B', 'Contact (verified): Text on arrival, do not knock', 'Gate code: on file and verified (code value never shown).', 'Building: apartment', 'ETA: 4 minutes, 0.4 miles away.'], 'llm_calls': 0, 'duplicate': False, 'decided_at': '2026-11-01T01:30:57.861888+00:00'}

Traces written to: evals/driver_intelligence/traces/demo_traces.jsonl (6 records)

Demo complete. Full loop shown: history -> memory -> alert -> feedback -> updated memory -> improved next alert.
```

## What to check in the output

- Scenario 1: the card starts with the leave restriction warning, then
  entrance, placement, contact, gate status only, building, and ETA.
- Scenario 2: the parcel locker instruction wins over the older
  "Leave at front door" instruction, and the trace step 6 names the
  winner, the loser, and the priority rule.
- Scenario 3a to 3c: the first card shows the gate code verified, the
  feedback trace shows verified to invalid, and the next card warns
  that access requires verification.
- Fallback check: the LLM outage trace step shows the deterministic
  fallback card decision and LLM calls 0.
- Nothing in the output contains a gate code value, and nothing is
  sent to anyone.
