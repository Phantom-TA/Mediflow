# MediFlow — System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          PATIENT (Phone Call)                        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ PSTN / SIP
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                            VAPI PLATFORM                             │
│                                                                      │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│   │  Deepgram    │    │  GPT-4o-mini │    │  Cartesia Sonic      │  │
│   │  Nova-3 STT  │───▶│  LLM         │───▶│  TTS                 │  │
│   └──────────────┘    └──────┬───────┘    └──────────────────────┘  │
│                              │                                        │
│                     Tool Call (HTTP POST)                             │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ HTTPS / JSON
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND (Render)                      │
│                                                                      │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                    Tool Layer (Routes)                       │   │
│   │  /find_doctors  /check_availability  /recommend_alternatives │   │
│   │  /book_appointment  /reschedule_appointment                  │   │
│   │  /cancel_appointment  /find_patient_appointments             │   │
│   └───────────────────────────┬─────────────────────────────────┘   │
│                               │                                       │
│   ┌───────────────────────────▼─────────────────────────────────┐   │
│   │                   Business Logic Layer                       │   │
│   │  AppointmentEngine  SlotEngine  ConflictResolver             │   │
│   └───────────────────────────┬─────────────────────────────────┘   │
│                               │                                       │
│   ┌───────────────────────────▼─────────────────────────────────┐   │
│   │              SQLAlchemy ORM + Session Management             │   │
│   └───────────────────────────┬─────────────────────────────────┘   │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ PostgreSQL Wire Protocol
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  SUPABASE PostgreSQL Database                        │
│                                                                      │
│   clinics │ doctors │ availability │ slots │ appointments            │
│   conversation_sessions │ conversation_state                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

### Vapi Platform
- Manages inbound phone call lifecycle
- Routes audio through Deepgram for STT
- Passes transcript turns to GPT-4o-mini
- Executes tool calls by HTTP POST to FastAPI
- Sends LLM text to Cartesia Sonic for TTS
- Returns audio to caller

### Deepgram Nova-3 (STT)
- Real-time streaming transcription
- Optimised for conversational speech
- Handles Indian English accents
- Provides word-level confidence scores

### GPT-4o-mini (LLM)
- Orchestrates conversation flow
- Decides when to call tools
- Formats tool results into natural speech
- **Never stores state** — reads from tool responses only
- Bound by system prompt to scope boundaries

### Cartesia Sonic (TTS)
- Neural TTS for natural-sounding responses
- Low-latency streaming synthesis
- Configured for a calm, professional voice

### FastAPI Backend (Render)
- Stateless REST API
- All business logic lives here
- Validates every incoming request
- Returns structured JSON responses
- Owns all appointment state transitions
- Handles concurrency via DB-level locking

### PostgreSQL (Supabase)
- Single source of truth
- Row-level locking for concurrent bookings
- UNIQUE constraints prevent double-booking
- Soft deletes (status flags) on appointments

---

## Data Flow: Happy Path Booking

```
1. Patient: "I'd like to book an appointment with a cardiologist"
2. Vapi STT: transcribes speech → text
3. LLM: intent=book, dept=Cardiology → calls find_doctors(department="Cardiology")
4. FastAPI: queries doctors table → returns list
5. LLM: presents options → "We have Dr. Suresh Rao and Dr. Priya Menon..."
6. Patient: "Dr. Suresh Rao please, tomorrow morning"
7. LLM: calls check_availability(doctor_id=X, date="tomorrow")
8. FastAPI: queries slots table → returns available slots
9. LLM: presents options → "Available at 9:00 AM, 9:15 AM, 9:30 AM..."
10. Patient: "9:00 AM works"
11. LLM: confirms details → "To confirm: Dr. Suresh Rao, June 23rd at 9:00 AM, for Cardiology?"
12. Patient: "Yes"
13. LLM: calls book_appointment(doctor_id, slot_id, patient_name, patient_phone)
14. FastAPI: BEGIN TRANSACTION
         → SELECT slot WHERE id=X FOR UPDATE
         → if available: INSERT appointment, UPDATE slot.is_available=false
         → COMMIT
15. FastAPI: returns { success: true, appointment_id: "...", confirmation: "..." }
16. LLM: "Your appointment is confirmed with Dr. Suresh Rao on June 23rd at 9:00 AM."
```

---

## Data Flow: Conflict Resolution

```
1. Patient requests slot that is already booked
2. FastAPI: book_appointment → returns { success: false, reason: "slot_unavailable" }
3. LLM: calls recommend_alternatives(doctor_id, date, specialty)
4. FastAPI: queries slots table → returns ranked alternatives
5. LLM: presents alternatives → "That slot is taken. Next available times are..."
6. Patient: selects alternative
7. → Continues as Happy Path from step 13
```

---

## Data Flow: Mid-Conversation Correction

```
1. Patient confirms "Dr. Suresh Rao"
2. LLM stores in tool call context (not in its own memory)
3. Patient: "Actually, can I switch to Dr. Priya Menon?"
4. LLM: calls check_availability(doctor_id=Y, date=...)
5. → Continues from step 8 above with new doctor
```

---

## Conversation State Model

State is stored in `conversation_sessions` and `conversation_state` tables.

Each Vapi call has a `call_id`. On every tool call, the backend:
1. Reads current state for `call_id`
2. Updates state with new confirmed values
3. Returns state snapshot in tool response

**State fields:**
```json
{
  "call_id": "vapi-call-uuid",
  "intent": "book | reschedule | cancel | unknown",
  "patient_name": "string | null",
  "patient_phone": "string | null",
  "selected_department": "string | null",
  "selected_doctor_id": "uuid | null",
  "selected_slot_id": "uuid | null",
  "current_appointment_id": "uuid | null",
  "confirmation_pending": "boolean",
  "last_updated": "timestamp"
}
```

---

## Security Model

- All FastAPI endpoints require an `X-Vapi-Secret` header (shared secret)
- Supabase connection uses service-role key (server-side only)
- No patient PII in logs
- Phone numbers stored in hashed form in audit logs (plain in appointments table)
- Rate limiting: 10 req/s per call_id

---

## Deployment Architecture

```
Render (FastAPI)
  └── Web Service: mediflow-api
      ├── Python 3.11
      ├── Uvicorn + Gunicorn
      ├── Environment: SUPABASE_URL, SUPABASE_KEY, VAPI_SECRET
      └── Health check: GET /health

Supabase (PostgreSQL)
  ├── Region: ap-south-1 (Mumbai) — closest to Bengaluru
  ├── Connection pooling: PgBouncer (transaction mode)
  └── Backups: daily

Vapi
  ├── Phone number: provisioned in Vapi dashboard
  ├── Assistant: mediflow-receptionist
  └── Webhook: POST https://mediflow-api.onrender.com/vapi/tool
```

---

## Project Directory Structure

```
mediflow/
├── docs/
│   ├── context.md
│   ├── architecture.md
│   ├── schema.md
│   ├── api_contracts.md
│   └── evaluation_spec.md
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── clinic.py
│   │   │   ├── doctor.py
│   │   │   ├── availability.py
│   │   │   ├── slot.py
│   │   │   ├── appointment.py
│   │   │   └── conversation.py
│   │   ├── schemas/
│   │   │   └── *.py
│   │   ├── routers/
│   │   │   └── tools.py
│   │   ├── services/
│   │   │   ├── appointment_engine.py
│   │   │   ├── slot_engine.py
│   │   │   └── conflict_resolver.py
│   │   └── core/
│   │       └── security.py
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   └── requirements.txt
├── data/
│   ├── doctors.json
│   ├── departments.json
│   ├── availability.json
│   └── source_urls.md
├── agent/
│   ├── system_prompt.txt
│   ├── tool_definitions.json
│   └── vapi_config.json
├── eval/
│   ├── scenarios/
│   ├── runner.py
│   ├── verifier.py
│   └── metrics.py
├── scripts/
│   ├── seed_database.py
│   └── generate_slots.py
├── tests/
│   ├── test_models.py
│   ├── test_slots.py
│   ├── test_appointments.py
│   ├── test_endpoints.py
│   └── test_eval.py
├── .env.example
├── docker-compose.yml
└── README.md
```
