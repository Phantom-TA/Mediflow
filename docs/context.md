# MediFlow — Project Context

## Project Overview

MediFlow is a production-grade Voice AI Receptionist built for **Apollo Hospital, Bannerghatta Road, Bengaluru**. It handles inbound patient calls and supports:

- Appointment Booking
- Appointment Rescheduling
- Appointment Cancellation
- Conflict Resolution
- Clarification Questions
- Recovery From User Mistakes
- Mid-Conversation Changes Of Mind

The system behaves as a trained hospital receptionist — not a chatbot. It speaks naturally, confirms details before acting, and never invents information.

---

## Hospital: Apollo Hospital Bannerghatta Road

- **Address:** 154/11, Opp. IIM-B, Bannerghatta Road, Bengaluru, Karnataka 560076
- **Phone:** 1066 / +91 80 2682 4444
- **Website:** https://www.apollohospitals.com/hospitals/bangalore/bannerghatta-road/
- **Specialties (sourced from Apollo website):**
  - Cardiology
  - Neurology
  - Orthopaedics
  - Oncology
  - Gastroenterology
  - Nephrology
  - Urology
  - Pulmonology
  - Endocrinology
  - Gynaecology & Obstetrics
  - Paediatrics
  - General Medicine
  - Dermatology
  - Ophthalmology
  - ENT (Ear, Nose & Throat)

---

## Core Design Principles

### 1. LLM Never Owns State
The backend is the single source of truth. The LLM orchestrates tool calls and presents information. It does NOT store, infer, or hallucinate state.

**State lives in PostgreSQL (Supabase):**
- `intent` — what the patient wants (book / reschedule / cancel)
- `patient_name` — extracted and confirmed
- `patient_phone` — extracted and confirmed
- `selected_department` — chosen specialty
- `selected_doctor` — chosen doctor
- `selected_slot` — chosen time slot
- `current_appointment` — for reschedule/cancel flows

### 2. Success = Database State
The measure of success is **not** what the LLM said. The measure of success is:
- Appointment row exists in `appointments` table
- Slot row is marked `is_available = false`
- Appointment is linked to correct doctor and patient

### 3. Real Data Only
All doctors, departments, and schedules are sourced from the real Apollo Hospital Bannerghatta Road website. Source URLs are stored per-record. No invented data.

---

## Scope Boundaries

The agent **will NOT**:
- Provide medical advice
- Access or integrate with Apollo's internal HIS/EMR systems
- Handle billing or insurance queries
- Book emergency services
- Promise anything without backend confirmation

The agent **will**:
- Confirm name, phone, department, doctor, and slot before booking
- Offer alternatives when the preferred slot or doctor is unavailable
- Handle corrections and mind-changes gracefully
- Confirm every completed action with the slot, doctor, and date

---

## Stakeholder Expectations

| Stakeholder      | Expectation                                              |
|------------------|----------------------------------------------------------|
| Patient          | Natural, clear conversation; confirmed appointments      |
| Hospital Admin   | Accurate records; no ghost bookings; reliable audit log  |
| Evaluation Panel | ≥95% task success; ≤2% hallucination rate; low latency   |

---

## Latency Targets

| Metric       | Target   |
|--------------|----------|
| p50 latency  | < 1.5 s  |
| p95 latency  | < 3.0 s  |
| Tool call RT | < 500 ms |

Latency is measured from end of patient speech to start of agent speech (TTFS — Time To First Speech).

---

## Non-Goals

- No real-time sync with Apollo's production systems
- No payment processing
- No multi-language support (English only for v1)
- No SMS/email confirmation (future phase)
- No escalation to live agent (future phase)
