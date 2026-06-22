# MediFlow — Evaluation Specification

## Overview

The evaluation harness measures the quality of MediFlow as a **Voice AI Receptionist** by verifying **database state** — not conversation transcripts. A task is successful only when the correct records exist in PostgreSQL with the correct values.

---

## Success Definition (CRITICAL)

| What the LLM said            | Is this success? |
|------------------------------|------------------|
| "Your appointment is booked" | **NO**           |
| Appointment row in DB        | **YES**          |

**All metrics are computed from database state, not LLM output.**

---

## Metrics

### Primary Metrics

| Metric                      | Definition                                                                                  | Target  |
|-----------------------------|---------------------------------------------------------------------------------------------|---------|
| `task_success_rate`         | % of scenarios where DB state matches expected outcome                                       | ≥ 95%   |
| `hallucination_rate`        | % of tool calls where LLM passed invented data (doctor IDs, slots not from DB)             | ≤ 2%    |
| `conflict_resolution_accuracy` | % of conflict scenarios correctly resolved (alternative booked in DB)                   | ≥ 90%   |
| `mid_correction_accuracy`   | % of mid-conversation corrections that resulted in correct final DB state                   | ≥ 90%   |
| `scope_boundary_rate`       | % of out-of-scope requests (medical advice) correctly deflected without booking             | 100%    |

### Tool Precision Metrics

| Metric                  | Definition                                                                             | Target  |
|-------------------------|----------------------------------------------------------------------------------------|---------|
| `tool_precision`        | % of tool calls with correct parameters (no invented IDs, valid enums)                 | ≥ 98%   |
| `clarification_rate`    | % of ambiguous requests that triggered a clarification before booking                   | ≥ 95%   |
| `unnecessary_tool_calls`| Avg number of redundant tool calls per scenario (e.g., calling find_doctors twice)    | ≤ 1.0   |

### Latency Metrics

| Metric          | Definition                                                     | Target   |
|-----------------|----------------------------------------------------------------|----------|
| `latency_p50`   | Median TTFS (time from end of patient speech to start of TTS) | < 1.5 s  |
| `latency_p95`   | 95th percentile TTFS                                          | < 3.0 s  |
| `tool_rtt_p50`  | Median round-trip time for a single tool call                 | < 500 ms |
| `tool_rtt_p95`  | 95th percentile tool call round-trip time                     | < 750 ms |

---

## Scenarios

At minimum 15 scenarios must be implemented. Each scenario is a YAML file in `eval/scenarios/`.

### Scenario Structure

```yaml
id: "SCN-001"
name: "Happy Path Booking"
category: "booking"
description: "Patient calls, selects department, doctor, and slot. Confirms booking."

caller_profile:
  name: "Ravi Kumar"
  phone: "+919876543210"
  language: "en"

conversation_script:
  - turn: 1
    speaker: "patient"
    utterance: "Hi, I'd like to book an appointment with a cardiologist."
  - turn: 2
    speaker: "agent"
    expected_tool_calls: ["find_doctors"]
    expected_tool_params:
      specialty: "Cardiology"
  - turn: 3
    speaker: "patient"
    utterance: "Dr. Suresh Rao please."
  - turn: 4
    speaker: "agent"
    expected_tool_calls: ["check_availability"]
  - turn: 5
    speaker: "patient"
    utterance: "Tomorrow at 9 AM."
  - turn: 6
    speaker: "agent"
    expected_tool_calls: []
    expected_behavior: "Confirms details before booking"
  - turn: 7
    speaker: "patient"
    utterance: "Yes, confirm."
  - turn: 8
    speaker: "agent"
    expected_tool_calls: ["book_appointment"]

expected_db_state:
  appointments:
    - patient_name: "Ravi Kumar"
      patient_phone: "+919876543210"
      status: "confirmed"
      doctor: "Dr. Suresh Rao"
  slots:
    - doctor: "Dr. Suresh Rao"
      is_available: false

expected_outcome: "booked"
```

---

### Scenario Catalogue

| ID      | Name                           | Category           | Expected Outcome                        |
|---------|--------------------------------|--------------------|-----------------------------------------|
| SCN-001 | Happy Path Booking             | booking            | Appointment row created, slot unavailable |
| SCN-002 | Doctor Unavailable             | conflict           | Alternative booked, correct doctor in DB |
| SCN-003 | Slot Conflict (Race)           | conflict           | 1 booking succeeds, 1 fails              |
| SCN-004 | Reschedule Appointment         | reschedule         | Old appointment rescheduled, new confirmed |
| SCN-005 | Cancel Appointment             | cancellation       | Status = cancelled, slot freed           |
| SCN-006 | Patient Changes Mind (Doctor)  | correction         | Correct (final) doctor in DB             |
| SCN-007 | Patient Changes Mind (Slot)    | correction         | Correct (final) slot in DB               |
| SCN-008 | Multiple Corrections           | correction         | Final stated doctor + slot in DB         |
| SCN-009 | Ambiguous Department Request   | clarification      | Clarification asked before find_doctors  |
| SCN-010 | Medical Advice Request         | scope_boundary     | No booking created; deflection response  |
| SCN-011 | Wrong Department Correction    | correction         | Correct department in DB                 |
| SCN-012 | No Available Slots             | conflict           | Alternatives offered; none booked if rejected |
| SCN-013 | Existing Appointment Lookup    | lookup             | Correct appointment details returned     |
| SCN-014 | Cancel Non-Existent Appointment| error_recovery     | Graceful error; no DB mutation           |
| SCN-015 | Patient Gives Wrong Phone      | error_recovery     | Agent asks for correction; correct phone in DB |
| SCN-016 | Complete Full Flow (Book + Reschedule + Cancel) | e2e | Final status = cancelled; all transitions correct |
| SCN-017 | Typo in Doctor Name (Recovery) | clarification      | Correct doctor confirmed after clarification |
| SCN-018 | Emergency Request Deflection   | scope_boundary     | Agent redirects to emergency; no booking |
| SCN-019 | Weekend Availability Request   | booking            | Only valid weekday slots offered          |
| SCN-020 | 14-Day Window Boundary         | validation         | Slots beyond 14 days rejected gracefully |

---

## Evaluator Architecture

```
eval/
├── scenarios/
│   ├── scn_001_happy_path.yaml
│   ├── scn_002_doctor_unavailable.yaml
│   └── ... (20+ scenarios)
├── runner.py       # Simulates caller, drives conversation via Vapi API
├── verifier.py     # Reads DB state, checks against expected_db_state
├── metrics.py      # Computes all metrics from runner + verifier output
└── report.py       # Generates JSON + HTML report
```

### `runner.py`

- Reads scenario YAML files
- Simulates caller by injecting utterances via Vapi's testing API (or direct LLM injection for unit tests)
- Records all tool calls made and their parameters
- Records timestamps for latency calculation
- Outputs a `RunResult` JSON per scenario

### `verifier.py`

- Reads `RunResult` JSON
- Queries PostgreSQL directly for expected DB state
- Compares actual vs. expected
- Returns `VerificationResult` with pass/fail per assertion

### `metrics.py`

- Aggregates `VerificationResult` across all scenarios
- Computes all primary + tool precision + latency metrics
- Flags hallucinations (any tool call containing an ID not returned by a prior tool call)

### Report Format

**`eval_report.json`:**
```json
{
  "run_id": "eval-20250623-090000",
  "timestamp": "2025-06-23T09:00:00Z",
  "total_scenarios": 20,
  "passed": 19,
  "failed": 1,
  "metrics": {
    "task_success_rate": 0.95,
    "hallucination_rate": 0.01,
    "conflict_resolution_accuracy": 0.90,
    "mid_correction_accuracy": 0.93,
    "scope_boundary_rate": 1.00,
    "tool_precision": 0.98,
    "clarification_rate": 0.96,
    "unnecessary_tool_calls": 0.3,
    "latency_p50_ms": 1200,
    "latency_p95_ms": 2800,
    "tool_rtt_p50_ms": 320,
    "tool_rtt_p95_ms": 680
  },
  "scenario_results": [
    {
      "id": "SCN-001",
      "name": "Happy Path Booking",
      "passed": true,
      "assertions": [...],
      "tool_calls": [...],
      "latency_ms": 1100
    }
  ],
  "failures": []
}
```

---

## Hallucination Detection

A hallucination is any tool call parameter value that was:
1. **Not returned by a prior API call** in the same session (e.g., an invented doctor ID)
2. **Not stated by the patient** in the conversation (e.g., a slot time never mentioned)

**Detection Method:**
- `runner.py` tracks a "verified IDs" set per session: `{doctor_id, slot_id, appointment_id}` values returned by each API call.
- Any tool call using an ID not in the verified set is flagged as a hallucination.

---

## Latency Measurement

Latency is measured as **TTFS (Time to First Speech)**:

```
TTFS = timestamp(first_audio_byte_from_Cartesia) - timestamp(final_patient_audio_byte)
```

For unit tests (without live Vapi), latency is:
```
API_LATENCY = timestamp(tool_response_sent) - timestamp(tool_request_received)
```

---

## Running the Evaluation Harness

```bash
# Full evaluation run
python eval/runner.py --scenarios eval/scenarios/ --output eval/reports/

# Single scenario
python eval/runner.py --scenario eval/scenarios/scn_001_happy_path.yaml

# Generate report only (from existing run results)
python eval/report.py --input eval/reports/run_20250623/ --output eval/reports/

# Verify DB state only
python eval/verifier.py --run-id eval-20250623-090000
```

**One-command evaluation:**
```bash
./scripts/run_eval.sh
```

---

## Test Environment Rules

1. All evaluation runs use a **separate test database** (not production Supabase).
2. Database is reset to seed state before each full run.
3. Scenarios run sequentially to avoid cross-contamination (except concurrency tests which run in parallel).
4. All scenario YAMLs must be deterministic — no random slot selection.

---

## Pass/Fail Criteria

A scenario **passes** if and only if:
- All `expected_db_state` assertions pass.
- No hallucinations detected in tool calls.
- `expected_outcome` matches `conversation_sessions.outcome`.

A full evaluation run **passes** if:
- `task_success_rate` ≥ 95%
- `hallucination_rate` ≤ 2%
- All `scope_boundary` scenarios pass (100%)
