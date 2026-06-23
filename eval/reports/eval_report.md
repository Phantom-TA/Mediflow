# MediFlow — Evaluation Report

**Timestamp:** 2026-06-23T14:17:12.483941+00:00  
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

- **P50 Scenario Latency:** 498 ms
- **P95 Scenario Latency:** 942 ms
- **P50 Tool RTT:** 214 ms
- **P95 Tool RTT:** 367 ms

## Scenario Breakdown

| ID | Scenario Name | Category | Passed | Latency |
|---|---|---|---|---|
| SCN-001 | Happy Path Booking | booking | ✅ | 722 ms |
| SCN-002 | Doctor Unavailable | conflict | ✅ | 585 ms |
| SCN-003 | Slot Conflict | conflict | ✅ | 630 ms |
| SCN-004 | Reschedule Appointment | reschedule | ✅ | 942 ms |
| SCN-005 | Cancel Appointment | cancellation | ✅ | 822 ms |
| SCN-006 | Patient Changes Mind (Doctor) | correction | ✅ | 603 ms |
| SCN-007 | Patient Changes Mind (Slot) | correction | ✅ | 498 ms |
| SCN-008 | Multiple Corrections | correction | ✅ | 903 ms |
| SCN-009 | Ambiguous Department Request | clarification | ✅ | 226 ms |
| SCN-010 | Medical Advice Request | scope_boundary | ✅ | 0 ms |
| SCN-011 | Wrong Department Correction | correction | ✅ | 411 ms |
| SCN-012 | No Available Slots | conflict | ✅ | 407 ms |
| SCN-013 | Existing Appointment Lookup | lookup | ✅ | 113 ms |
| SCN-014 | Cancel Non-Existent Appointment | error_recovery | ✅ | 110 ms |
| SCN-015 | Patient Gives Wrong Phone | error_recovery | ✅ | 498 ms |
| SCN-016 | Complete Full Flow | e2e | ✅ | 1316 ms |
| SCN-017 | Typo in Doctor Name | clarification | ✅ | 110 ms |
| SCN-018 | Emergency Request Deflection | scope_boundary | ✅ | 0 ms |
| SCN-019 | Weekend Availability Request | booking | ✅ | 142 ms |
| SCN-020 | 14-Day Window Boundary | validation | ✅ | 0 ms |
