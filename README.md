# MediFlow — Voice AI scheduling Engine

MediFlow is a production-grade, transaction-safe automated scheduling system and Voice AI Receptionist built for **Apollo Hospital, Bannerghatta Road, Bengaluru**. 

It enables patients to search for real practitioners, query availability windows, book/reschedule/cancel appointments, and get ranked alternative recommendations when preferred slots are busy—all handled over a voice channel via webhook integrations with **Vapi**.

---

## 🚀 Key Features

* **Real Apollo Hospital Dataset:** Contains profiles, specialties, and schedules for 17 real practitioners across 15 medical departments.
* **Rolling 14-Day Slot Engine:** Timezone-aware generator (converting Indian Standard Time to UTC) with database idempotency to maintain available 15-minute slots.
* **Concurrency-Safe Appointment Engine:** Protects appointments from double-booking under high concurrent load using PostgreSQL transaction row-level locks (`SELECT FOR UPDATE NOWAIT`).
* **FastAPI receptionist Tool Layer:** Exposes 7 secure endpoints authenticated via `X-Vapi-Secret` headers, along with a unified webhook router that handles multi-tool calls and maps errors to a strict API schema contract.
* **Scheduling Intelligence & Fallbacks:** Automatically maps user specialty aliases (e.g. "heart" to "Cardiology", "kid" to "Pediatrics & Neonatology") and ranks alternative available slots using a weighted similarity algorithm.
* **Conversational Evaluation Harness:** A testing pipeline that simulates 20 distinct dialog flows (bookings, cancellations, corrections, medical deflections) and validates correctness by checking the state of the database.

---

## 🛠️ Tech Stack
- **Backend:** FastAPI (Python 3.12)
- **Database ORM:** SQLAlchemy with Alembic Migrations
- **Database:** PostgreSQL (Supabase / Neon)
- **Containerization:** Docker & Docker Compose
- **Testing:** Pytest & Ruff (Linter)

---

## 📂 Repository Structure
```text
├── agent/                       # Vapi voice agent configurations
│   ├── system_prompt.txt        # LLM system prompt & deflection rules
│   ├── tool_definitions.json    # Vapi custom tools schema definitions
│   └── vapi_config.json         # Complete assistant deployment payload
├── backend/
│   ├── alembic/                 # Alembic DB migration environment
│   ├── app/
│   │   ├── models/              # SQLAlchemy database tables
│   │   ├── routers/             # API endpoints (tools and unified webhook)
│   │   ├── schemas/             # Pydantic validation schemas
│   │   └── services/            # Slot engines, bookings, & similarity rankers
│   ├── requirements.txt         # Backend python dependencies
│   └── pytest.ini               # Pytest configurations
├── data/                        # Seeding datasets (doctors, departments)
├── docs/                        # Specifications, API contracts & deployment guides
├── eval/                        # Evaluation Harness
│   ├── scenarios/               # 20 YAML simulation scenarios
│   ├── runner.py                # TestClient scenario executor
│   ├── verifier.py              # PostgreSQL database verifier
│   ├── metrics.py               # Aggregates accuracy, latency, precision
│   └── report.py                # Compiles markdown/JSON evaluation reports
├── scripts/                     # Seeding, slot generation CLI, and run helpers
├── tests/                       # Unit, integration, and concurrency pytest suite
├── Dockerfile                   # Production build recipe
└── docker-compose.yml           # Local multi-container orchestrator
```

---

## 💻 Local Quickstart

### 1. Prerequisite Environments
- Python 3.12+ installed
- PostgreSQL database instance running (or Supabase/Neon URL)

### 2. Installation
Clone the repository, configure virtual environment, and install dependencies:
```powershell
# Navigate into backend/
cd backend
python -m venv .venv
# Activate virtual environment
.\.venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `backend/.env` file with your database URL and Vapi secret key:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mediflow
DATABASE_URL_TEST=postgresql://postgres:postgres@localhost:5432/mediflow_test
VAPI_SECRET=local-dev-secret
```

### 4. Database Setup & Seeding
Run migrations to set up the tables, then seed the hospital dataset and pre-generate scheduling slots:
```powershell
# Run migrations
alembic upgrade head

# Seed doctors and departments
python ..\scripts\seed_database.py

# Pre-generate 14 days of slots
python ..\scripts\generate_slots.py
```

### 5. Start Server
Run the FastAPI application locally:
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🐳 Docker Quickstart (One-Command Setup)

You can run the entire environment (Postgres DB, Migrator/Seeder, and Web Server) in Docker with a single command:
```bash
docker-compose up --build
```
This will automatically:
1. Fire up a PostgreSQL Alpine container on port `5432`.
2. Run migrations, seed the doctor data, and pre-generate available slots.
3. Start the FastAPI API Server listening on `http://localhost:8000`.

---

## 🧪 Run Unit & Integration Tests
To execute all 67 test cases (including the multi-threaded concurrency booking lock test):
```powershell
pytest
```
*Note: The test suite uses nested transaction savepoints (`begin_nested()`) to guarantee complete test isolation and zero database pollution across test runs.*

---

## 📊 Run conversational Evaluation Harness
To execute the 20 conversational scenarios and compile the metrics report:
```powershell
python eval/report.py
```
This produces the following reports under the `eval/reports/` folder:
- **`eval_report.json`**: Structural JSON metrics payload containing success rate, latency statistics, and precision.
- **`eval_report.md`**: A compiled markdown report summarizing the execution.

---

## 📖 Additional Documentation
For deep-dives, refer to:
- [Deployment Guide](file:///e:/mediflow/docs/deployment_guide.md) — Production Render/Vapi guide.
- [API Contracts](file:///e:/mediflow/docs/api_contracts.md) — Endpoint requests/responses specification.
- [Architecture](file:///e:/mediflow/docs/architecture.md) — Internals flow and database concurrency locking design.
