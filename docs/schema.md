# MediFlow — Database Schema

## Overview

The database is hosted on **Supabase PostgreSQL** (region: ap-south-1).
All UUIDs use `gen_random_uuid()`. All timestamps are stored in UTC.

---

## Tables

### `clinics`

Stores the hospital/clinic entity. Supports future multi-clinic expansion.

```sql
CREATE TABLE clinics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    address         TEXT NOT NULL,
    city            TEXT NOT NULL,
    state           TEXT NOT NULL,
    phone           TEXT,
    website_url     TEXT,
    source_url      TEXT NOT NULL,   -- URL where this data was sourced from
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Notes:**
- `source_url`: the Apollo webpage from which clinic data was verified.

---

### `doctors`

Stores real doctors from Apollo Hospital Bannerghatta Road.

```sql
CREATE TABLE doctors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    salutation      TEXT NOT NULL DEFAULT 'Dr.',
    specialty       TEXT NOT NULL,           -- e.g. "Cardiology"
    department      TEXT NOT NULL,           -- e.g. "Department of Cardiology"
    qualifications  TEXT NOT NULL,           -- e.g. "MBBS, MD, DM (Cardiology)"
    experience_years INT,
    designation     TEXT,                    -- e.g. "Senior Consultant"
    languages       TEXT[],                  -- e.g. ["English", "Kannada", "Hindi"]
    source_url      TEXT NOT NULL,           -- Apollo doctor profile URL
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_doctors_clinic_id ON doctors(clinic_id);
CREATE INDEX idx_doctors_specialty ON doctors(specialty);
CREATE INDEX idx_doctors_is_active ON doctors(is_active);
```

**Notes:**
- Every doctor must have a `source_url` pointing to their Apollo profile.
- `is_active = false` is used when a doctor is no longer available (soft delete).
- `languages` is used by the scheduling intelligence for language-preference matching (future).

---

### `availability`

Defines weekly recurring availability windows for each doctor.
Slot generation reads from this table to produce concrete time slots.

```sql
CREATE TABLE availability (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id       UUID NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    day_of_week     SMALLINT NOT NULL,       -- 0=Monday, 6=Sunday (ISO: 1=Monday, 7=Sunday)
    start_time      TIME NOT NULL,           -- e.g. 09:00:00
    end_time        TIME NOT NULL,           -- e.g. 13:00:00
    slot_duration   SMALLINT NOT NULL DEFAULT 15,  -- minutes
    timezone        TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    is_active       BOOLEAN NOT NULL DEFAULT true,
    source_url      TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT valid_day_of_week CHECK (day_of_week BETWEEN 0 AND 6),
    CONSTRAINT valid_times CHECK (end_time > start_time),
    CONSTRAINT valid_slot_duration CHECK (slot_duration IN (10, 15, 20, 30))
);

CREATE INDEX idx_availability_doctor_id ON availability(doctor_id);
CREATE INDEX idx_availability_day ON availability(day_of_week);
```

**Notes:**
- `day_of_week`: 0=Monday through 6=Sunday (Python `weekday()` convention).
- Multiple rows per doctor allowed (e.g., morning and evening sessions on the same day).
- Slot generation uses `DATEADD` to materialise these windows into the `slots` table.

---

### `slots`

Concrete, materialised appointment time slots. Generated 14 days ahead by the slot engine.

```sql
CREATE TABLE slots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id       UUID NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    availability_id UUID NOT NULL REFERENCES availability(id) ON DELETE CASCADE,
    slot_start      TIMESTAMPTZ NOT NULL,   -- e.g. 2025-06-23 03:30:00+00 (09:00 IST)
    slot_end        TIMESTAMPTZ NOT NULL,
    is_available    BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_doctor_slot UNIQUE (doctor_id, slot_start),
    CONSTRAINT valid_slot_window CHECK (slot_end > slot_start)
);

CREATE INDEX idx_slots_doctor_id ON slots(doctor_id);
CREATE INDEX idx_slots_slot_start ON slots(slot_start);
CREATE INDEX idx_slots_is_available ON slots(is_available);
CREATE INDEX idx_slots_doctor_date ON slots(doctor_id, slot_start) WHERE is_available = true;
```

**Notes:**
- `UNIQUE(doctor_id, slot_start)` is the primary double-booking guard at the DB level.
- `is_available = false` is set atomically inside a transaction when a slot is booked.
- `slot_start` is stored in UTC; conversion to IST happens at the API layer.
- The partial index on `(doctor_id, slot_start) WHERE is_available = true` optimises availability queries.

---

### `appointments`

The core booking record. Created when a patient books a slot.

```sql
CREATE TABLE appointments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slot_id             UUID NOT NULL REFERENCES slots(id) ON DELETE RESTRICT,
    doctor_id           UUID NOT NULL REFERENCES doctors(id) ON DELETE RESTRICT,
    clinic_id           UUID NOT NULL REFERENCES clinics(id) ON DELETE RESTRICT,
    patient_name        TEXT NOT NULL,
    patient_phone       TEXT NOT NULL,
    reason              TEXT,                        -- optional, brief description
    status              TEXT NOT NULL DEFAULT 'confirmed',
    cancellation_reason TEXT,
    original_slot_id    UUID REFERENCES slots(id),  -- set on reschedule
    call_id             TEXT,                        -- Vapi call ID for traceability
    booked_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    cancelled_at        TIMESTAMPTZ,
    rescheduled_at      TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT valid_status CHECK (status IN ('confirmed', 'cancelled', 'rescheduled', 'completed', 'no_show')),
    CONSTRAINT uq_slot_appointment UNIQUE (slot_id)   -- one appointment per slot
);

CREATE INDEX idx_appointments_patient_phone ON appointments(patient_phone);
CREATE INDEX idx_appointments_doctor_id ON appointments(doctor_id);
CREATE INDEX idx_appointments_status ON appointments(status);
CREATE INDEX idx_appointments_call_id ON appointments(call_id);
```

**Notes:**
- `UNIQUE(slot_id)` provides an additional DB-level guard (slot-appointment 1:1).
- Status transitions:
  - `confirmed` → `cancelled` (patient cancels)
  - `confirmed` → `rescheduled` (patient reschedules; a new `appointments` row is created)
  - `confirmed` → `completed` (post-appointment, set by admin)
  - `confirmed` → `no_show` (patient did not attend)
- On reschedule:
  - Old appointment: `status = 'rescheduled'`, `rescheduled_at = now()`
  - Old slot: `is_available = true` (freed)
  - New appointment: `status = 'confirmed'`, `original_slot_id` = old slot id
  - New slot: `is_available = false`

---

### `conversation_sessions`

Tracks each Vapi call session.

```sql
CREATE TABLE conversation_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id         TEXT NOT NULL UNIQUE,   -- Vapi's call UUID
    patient_phone   TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at        TIMESTAMPTZ,
    outcome         TEXT,                   -- "booked", "cancelled", "rescheduled", "abandoned", "out_of_scope"
    appointment_id  UUID REFERENCES appointments(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sessions_call_id ON conversation_sessions(call_id);
CREATE INDEX idx_sessions_patient_phone ON conversation_sessions(patient_phone);
```

---

### `conversation_state`

Persists mid-conversation state keyed by `call_id`. Updated on every tool invocation.

```sql
CREATE TABLE conversation_state (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id                 TEXT NOT NULL UNIQUE REFERENCES conversation_sessions(call_id),
    intent                  TEXT,           -- "book" | "reschedule" | "cancel" | "unknown"
    patient_name            TEXT,
    patient_phone           TEXT,
    selected_department     TEXT,
    selected_doctor_id      UUID REFERENCES doctors(id),
    selected_slot_id        UUID REFERENCES slots(id),
    current_appointment_id  UUID REFERENCES appointments(id),
    confirmation_pending    BOOLEAN NOT NULL DEFAULT false,
    last_updated            TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## Entity Relationship Diagram

```
clinics
  │
  ├──< doctors (clinic_id)
  │      │
  │      ├──< availability (doctor_id)
  │      │         │
  │      │         └──< slots (availability_id, doctor_id)
  │      │                   │
  │      │                   └──< appointments (slot_id, doctor_id, clinic_id)
  │      │
  │      └──< appointments (doctor_id)
  │
  └──< appointments (clinic_id)

conversation_sessions
  │
  ├──  conversation_state (call_id)
  └──  appointments (appointment_id)
```

---

## Key Constraints Summary

| Table          | Constraint                          | Purpose                          |
|----------------|-------------------------------------|----------------------------------|
| `slots`        | `UNIQUE(doctor_id, slot_start)`     | Prevent duplicate slot creation  |
| `appointments` | `UNIQUE(slot_id)`                   | Prevent double booking           |
| `doctors`      | `source_url NOT NULL`               | Enforce real data provenance     |
| `availability` | `CHECK(day_of_week BETWEEN 0 AND 6)`| Validate weekday values          |
| `availability` | `CHECK(end_time > start_time)`      | Prevent invalid windows          |
| `appointments` | `CHECK(status IN (...))`            | Enforce valid status transitions |

---

## Migrations

Managed by **Alembic**. All migrations live in `backend/alembic/versions/`.

Migration naming convention:
```
YYYYMMDD_HHMMSS_description.py
```

Example:
```
20250623_090000_create_initial_schema.py
```

Every migration must be:
- Idempotent where possible
- Reversible (include `downgrade()`)
- Tested in CI before merge
