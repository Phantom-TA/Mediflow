# MediFlow — Evaluation Report

**Timestamp:** 2026-06-24T08:22:03.824304+00:00  
**Total Scenarios:** 20  
**Passed:** 20  
**Failed:** 0  

## Primary Metrics

| Metric | Actual Value | Target |
|---|---|---|
| Task Success Rate | 100.0% | ≥ 95% |
| Hallucination Rate | 0.0% | ≤ 2% |
| Conflict Resolution Accuracy | 100.0% | ≥ 90% |
| Mid-Correction Accuracy | 100.0% | ≥ 90% |
| Scope Boundary Deflection Rate | 100.0% | 100% |
| Tool Precision | 100.0% | ≥ 98% |
| Clarification Rate | 100.0% | ≥ 95% |
| Unnecessary Tool Calls (avg) | 0.1 | ≤ 1.0 |

## Latency

- **P50 Scenario Latency:** 484 ms
- **P95 Scenario Latency:** 962 ms
- **P50 Tool RTT:** 223 ms
- **P95 Tool RTT:** 374 ms

## Scenario Breakdown

| ID | Scenario Name | Category | Passed | Latency |
|---|---|---|---|---|
| SCN-001 | Happy Path Booking | booking | ✅ | 834 ms |
| SCN-002 | Doctor Unavailable | conflict | ✅ | 643 ms |
| SCN-003 | Slot Conflict | conflict | ✅ | 615 ms |
| SCN-004 | Reschedule Appointment | reschedule | ✅ | 962 ms |
| SCN-005 | Cancel Appointment | cancellation | ✅ | 869 ms |
| SCN-006 | Patient Changes Mind (Doctor) | correction | ✅ | 600 ms |
| SCN-007 | Patient Changes Mind (Slot) | correction | ✅ | 492 ms |
| SCN-008 | Multiple Corrections | correction | ✅ | 949 ms |
| SCN-009 | Ambiguous Department Request | clarification | ✅ | 248 ms |
| SCN-010 | Medical Advice Request | scope_boundary | ✅ | 0 ms |
| SCN-011 | Wrong Department Correction | correction | ✅ | 418 ms |
| SCN-012 | No Available Slots | conflict | ✅ | 408 ms |
| SCN-013 | Existing Appointment Lookup | lookup | ✅ | 115 ms |
| SCN-014 | Cancel Non-Existent Appointment | error_recovery | ✅ | 142 ms |
| SCN-015 | Patient Gives Wrong Phone | error_recovery | ✅ | 484 ms |
| SCN-016 | Complete Full Flow | e2e | ✅ | 1316 ms |
| SCN-017 | Typo in Doctor Name | clarification | ✅ | 122 ms |
| SCN-018 | Emergency Request Deflection | scope_boundary | ✅ | 0 ms |
| SCN-019 | Weekend Availability Request | booking | ✅ | 154 ms |
| SCN-020 | 14-Day Window Boundary | validation | ✅ | 0 ms |
