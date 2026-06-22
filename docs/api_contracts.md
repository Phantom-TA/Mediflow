# MediFlow — API Contracts

## Overview

All endpoints are served by the **FastAPI** backend deployed on Render.

**Base URL:** `https://mediflow-api.onrender.com`

**Authentication:** All endpoints require:
```
X-Vapi-Secret: <shared_secret>
Content-Type: application/json
```

**Error Response Shape (all errors):**
```json
{
  "success": false,
  "error_code": "SLOT_UNAVAILABLE",
  "error_message": "The requested slot is no longer available.",
  "data": null
}
```

**Error Codes:**
| Code                  | HTTP Status | Meaning                                      |
|-----------------------|-------------|----------------------------------------------|
| `SLOT_UNAVAILABLE`    | 409         | Slot already booked or doesn't exist         |
| `DOCTOR_NOT_FOUND`    | 404         | Doctor ID doesn't exist or is inactive       |
| `APPOINTMENT_NOT_FOUND` | 404       | Appointment ID doesn't exist                 |
| `PATIENT_NOT_FOUND`   | 404         | No appointments found for this phone         |
| `INVALID_DATE_RANGE`  | 400         | Date is in the past or beyond 14-day window  |
| `VALIDATION_ERROR`    | 422         | Missing or malformed request fields          |
| `CONCURRENT_CONFLICT` | 409         | Race condition; slot claimed by another call |
| `INTERNAL_ERROR`      | 500         | Unexpected server error                      |

---

## Endpoints

---

### `POST /tools/find_doctors`

**Purpose:** Find doctors by specialty or name. Called when the patient states a department or requests a specific doctor.

**Request:**
```json
{
  "call_id": "string (required)",
  "specialty": "string (optional)",
  "name_query": "string (optional)",
  "clinic_id": "string (optional, defaults to Apollo Bannerghatta)"
}
```

At least one of `specialty` or `name_query` must be provided.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "doctors": [
      {
        "id": "uuid",
        "name": "Dr. Suresh Rao",
        "specialty": "Cardiology",
        "department": "Department of Cardiology",
        "qualifications": "MBBS, MD, DM (Cardiology)",
        "experience_years": 18,
        "designation": "Senior Consultant",
        "next_available": "2025-06-23T09:00:00+05:30"
      }
    ],
    "total": 2
  }
}
```

**Notes:**
- Results are sorted by `experience_years DESC, name ASC`.
- `next_available` is the earliest available slot across the next 14 days.
- Returns only `is_active = true` doctors.

---

### `POST /tools/check_availability`

**Purpose:** Get available slots for a specific doctor on a specific date (or date range).

**Request:**
```json
{
  "call_id": "string (required)",
  "doctor_id": "uuid (required)",
  "date": "YYYY-MM-DD (required)",
  "date_end": "YYYY-MM-DD (optional, for range queries)"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "doctor": {
      "id": "uuid",
      "name": "Dr. Suresh Rao",
      "specialty": "Cardiology"
    },
    "date": "2025-06-23",
    "slots": [
      {
        "id": "uuid",
        "slot_start": "2025-06-23T09:00:00+05:30",
        "slot_end": "2025-06-23T09:15:00+05:30",
        "is_available": true
      },
      {
        "id": "uuid",
        "slot_start": "2025-06-23T09:15:00+05:30",
        "slot_end": "2025-06-23T09:30:00+05:30",
        "is_available": true
      }
    ],
    "total_available": 12
  }
}
```

**Notes:**
- Only returns slots where `is_available = true`.
- `slot_start` is always returned in IST (`+05:30`).
- If `date` is today, only future slots (after current time) are returned.
- Date must be within the next 14 days.

---

### `POST /tools/recommend_alternatives`

**Purpose:** When a preferred slot or doctor is unavailable, return ranked alternatives.

**Request:**
```json
{
  "call_id": "string (required)",
  "specialty": "string (required)",
  "preferred_doctor_id": "uuid (optional)",
  "preferred_date": "YYYY-MM-DD (required)",
  "preferred_time": "HH:MM (optional, 24h format)",
  "max_results": 5
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "alternatives": [
      {
        "rank": 1,
        "doctor": {
          "id": "uuid",
          "name": "Dr. Suresh Rao",
          "specialty": "Cardiology"
        },
        "slot": {
          "id": "uuid",
          "slot_start": "2025-06-23T09:30:00+05:30",
          "slot_end": "2025-06-23T09:45:00+05:30"
        },
        "reason": "Same doctor, next available slot",
        "score": 0.95
      },
      {
        "rank": 2,
        "doctor": {
          "id": "uuid",
          "name": "Dr. Priya Menon",
          "specialty": "Cardiology"
        },
        "slot": {
          "id": "uuid",
          "slot_start": "2025-06-23T10:00:00+05:30",
          "slot_end": "2025-06-23T10:15:00+05:30"
        },
        "reason": "Same specialty, same day",
        "score": 0.82
      }
    ]
  }
}
```

**Ranking Algorithm:**
| Factor                          | Weight |
|---------------------------------|--------|
| Same doctor                     | 40%    |
| Same specialty                  | 20%    |
| Closest time to preferred_time  | 20%    |
| Earliest available date         | 20%    |

**Notes:**
- Always returns at least 1 result (if any slot exists for the specialty in next 14 days).
- `score` is a float 0.0–1.0.

---

### `POST /tools/book_appointment`

**Purpose:** Atomically book an appointment slot.

**Request:**
```json
{
  "call_id": "string (required)",
  "slot_id": "uuid (required)",
  "doctor_id": "uuid (required)",
  "patient_name": "string (required)",
  "patient_phone": "string (required)",
  "reason": "string (optional)"
}
```

**Response (200 — success):**
```json
{
  "success": true,
  "data": {
    "appointment_id": "uuid",
    "doctor_name": "Dr. Suresh Rao",
    "specialty": "Cardiology",
    "slot_start": "2025-06-23T09:00:00+05:30",
    "slot_end": "2025-06-23T09:15:00+05:30",
    "patient_name": "Ravi Kumar",
    "patient_phone": "+919876543210",
    "status": "confirmed",
    "confirmation_message": "Appointment confirmed with Dr. Suresh Rao on Monday 23rd June at 9:00 AM."
  }
}
```

**Response (409 — slot unavailable):**
```json
{
  "success": false,
  "error_code": "SLOT_UNAVAILABLE",
  "error_message": "The 9:00 AM slot with Dr. Suresh Rao on June 23rd is no longer available.",
  "data": null
}
```

**Transaction Semantics:**
```
BEGIN
  SELECT * FROM slots WHERE id = :slot_id FOR UPDATE NOWAIT
  IF is_available = false → RAISE SLOT_UNAVAILABLE
  INSERT INTO appointments (...)
  UPDATE slots SET is_available = false WHERE id = :slot_id
COMMIT
```

**Notes:**
- `FOR UPDATE NOWAIT` ensures zero wait on concurrent requests — the second request fails immediately.
- `patient_phone` must include country code (e.g., `+91`).
- The `call_id` is stored in the appointments row for full traceability.

---

### `POST /tools/reschedule_appointment`

**Purpose:** Atomically move an appointment to a new slot.

**Request:**
```json
{
  "call_id": "string (required)",
  "appointment_id": "uuid (required)",
  "new_slot_id": "uuid (required)",
  "patient_phone": "string (required)"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "old_appointment_id": "uuid",
    "new_appointment_id": "uuid",
    "doctor_name": "Dr. Suresh Rao",
    "old_slot_start": "2025-06-23T09:00:00+05:30",
    "new_slot_start": "2025-06-24T10:00:00+05:30",
    "status": "confirmed",
    "confirmation_message": "Rescheduled to Tuesday 24th June at 10:00 AM with Dr. Suresh Rao."
  }
}
```

**Transaction Semantics:**
```
BEGIN
  SELECT * FROM appointments WHERE id = :appointment_id FOR UPDATE
  VERIFY patient_phone matches
  SELECT * FROM slots WHERE id = :new_slot_id FOR UPDATE NOWAIT
  IF new slot not available → RAISE SLOT_UNAVAILABLE
  
  UPDATE appointments SET status='rescheduled', rescheduled_at=now() WHERE id = :appointment_id
  UPDATE slots SET is_available=true WHERE id = old_slot_id
  
  INSERT INTO appointments (slot_id=new_slot_id, original_slot_id=old_slot_id, status='confirmed')
  UPDATE slots SET is_available=false WHERE id = :new_slot_id
COMMIT
```

**Notes:**
- The `patient_phone` check prevents one patient from rescheduling another patient's appointment.
- Old appointment `status` becomes `'rescheduled'`, not deleted.
- Old slot is freed (`is_available = true`).

---

### `POST /tools/cancel_appointment`

**Purpose:** Cancel a confirmed appointment.

**Request:**
```json
{
  "call_id": "string (required)",
  "appointment_id": "uuid (required)",
  "patient_phone": "string (required)",
  "reason": "string (optional)"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "appointment_id": "uuid",
    "doctor_name": "Dr. Suresh Rao",
    "slot_start": "2025-06-23T09:00:00+05:30",
    "status": "cancelled",
    "confirmation_message": "Your appointment with Dr. Suresh Rao on June 23rd at 9:00 AM has been cancelled."
  }
}
```

**Transaction Semantics:**
```
BEGIN
  SELECT * FROM appointments WHERE id = :appointment_id FOR UPDATE
  VERIFY patient_phone matches
  VERIFY status = 'confirmed'
  UPDATE appointments SET status='cancelled', cancelled_at=now(), cancellation_reason=:reason
  UPDATE slots SET is_available=true WHERE id = slot_id
COMMIT
```

---

### `POST /tools/find_patient_appointments`

**Purpose:** Look up a patient's existing appointments by phone number.

**Request:**
```json
{
  "call_id": "string (required)",
  "patient_phone": "string (required)",
  "status_filter": "string (optional, default: 'confirmed')"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "appointments": [
      {
        "id": "uuid",
        "doctor_name": "Dr. Suresh Rao",
        "specialty": "Cardiology",
        "slot_start": "2025-06-23T09:00:00+05:30",
        "slot_end": "2025-06-23T09:15:00+05:30",
        "status": "confirmed",
        "booked_at": "2025-06-20T14:30:00+05:30"
      }
    ],
    "total": 1
  }
}
```

**Notes:**
- Returns only future appointments by default.
- `status_filter` accepts: `confirmed`, `cancelled`, `rescheduled`, `all`.

---

### `GET /health`

**Purpose:** Health check for Render and monitoring.

**Response (200):**
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0",
  "timestamp": "2025-06-22T06:00:00Z"
}
```

---

## Vapi Tool Webhook

Vapi calls a single webhook URL for all tool invocations during a conversation.

**URL:** `POST /vapi/tool`

**Vapi Request Shape:**
```json
{
  "message": {
    "type": "tool-calls",
    "toolCallList": [
      {
        "id": "tool-call-uuid",
        "function": {
          "name": "find_doctors",
          "arguments": "{\"specialty\": \"Cardiology\", \"call_id\": \"vapi-call-uuid\"}"
        }
      }
    ],
    "call": {
      "id": "vapi-call-uuid",
      "phoneNumber": "+919876543210"
    }
  }
}
```

**Response Shape (Vapi expects):**
```json
{
  "results": [
    {
      "toolCallId": "tool-call-uuid",
      "result": "{...JSON string of tool response...}"
    }
  ]
}
```

---

## OpenAPI

The FastAPI app auto-generates OpenAPI 3.0 at:
- Swagger UI: `GET /docs`
- ReDoc: `GET /redoc`
- JSON schema: `GET /openapi.json`
