# MediFlow — Production Deployment Guide

This guide outlines step-by-step instructions to deploy the MediFlow FastAPI backend, database migrations, slot-generation cron jobs, and hook up the system with a live Vapi Voice Agent.

---

## 1. Database Setup
MediFlow requires a live PostgreSQL instance. We recommend **Supabase** or **Neon**.

1. Create a PostgreSQL project on [Supabase](https://supabase.com) or [Neon](https://neon.tech).
2. Retrieve the transaction connection string (e.g., `postgresql://postgres:[password]@db.supabase.co:5432/postgres` or pooling equivalent).
3. Save this connection string; you will need it for the application's environment variables (`DATABASE_URL`).

---

## 2. API Server Deployment (Render)
You can deploy the FastAPI application on [Render](https://render.com) using the root-level `Dockerfile`.

1. Sign in to Render and select **New +** > **Web Service**.
2. Connect your Git repository.
3. Configure the following settings:
   - **Environment:** `Docker`
   - **Build Context:** `.` (root directory)
   - **Dockerfile Path:** `./Dockerfile`
4. Add the following **Environment Variables**:
   - `DATABASE_URL`: *[Your production PostgreSQL connection string]*
   - `APP_ENV`: `production`
   - `VAPI_SECRET`: *[A secure random string of your choice for authenticating Vapi requests]*
5. Click **Deploy Web Service**.
6. Note down the public URL of your service (e.g., `https://mediflow-api.onrender.com`).
7. Verify the deploy by hitting the healthcheck endpoint: `GET https://your-domain.onrender.com/health` (should return `{"status": "ok"}`).

---

## 3. Database Migration, Seeding & Slot Generation

### A. Run Initial Migrations and Seed
To create tables and seed real Apollo Hospital doctor schedules:
1. Log in to your Render dashboard.
2. Open the deployed Web Service's **Shell** tab (or run locally with env pointing to prod DB).
3. Run the migrations:
   ```bash
   alembic upgrade head
   ```
4. Run the seed script:
   ```bash
   python scripts/seed_database.py
   ```

### B. Daily Slot Generation (Cron Job)
MediFlow operates on a rolling 14-day schedule. To automatically generate slots:
1. Create a **Cron Job** on Render or configure a scheduled task (e.g. GitHub Actions, AWS EventBridge, or Render Cron).
2. Set the cron expression to run once daily (e.g., `0 0 * * *`).
3. Set the environment variable `DATABASE_URL` pointing to your database.
4. Set the command to:
   ```bash
   python scripts/generate_slots.py
   ```
   *This script runs in under 2 seconds and generates missing slots idempotently using database constraints.*

---

## 4. Vapi Voice Agent Setup

To link your deployed backend with a live voice receptionist:

### Option A: Using the Vapi Dashboard (Manual)
1. Go to the [Vapi Dashboard](https://dashboard.vapi.ai) and sign in.
2. Click **Assistants** > **Create Assistant**.
3. Set up the following parameters:
   - **Assistant Name:** `MediFlow AI Receptionist`
   - **First Message:** `Hello, thank you for calling Apollo Hospital scheduling services. My name is MediFlow. How can I assist you today?`
   - **System Prompt:** Copy the entire text content from `agent/system_prompt.txt` into the instructions box.
4. Click **Tools** > **Create Tool**.
   - Create custom tools matching the schemas inside `agent/tool_definitions.json`.
   - Set the tool **Webhook URL** to your unified endpoint: `https://your-domain.onrender.com/vapi/tool`.
   - Add a custom request header: `X-Vapi-Secret` with the secret value you set in your server's environment variables.
5. Save the assistant configuration.

### Option B: Using the Vapi API (One-Click)
You can directly import the assistant with all tools using the Vapi API:
1. Retrieve your Vapi Private API Key from your Vapi profile.
2. Send a POST request to `https://api.vapi.ai/assistant` using the JSON content inside `agent/vapi_config.json`:
   ```bash
   curl -X POST https://api.vapi.ai/assistant \
     -H "Authorization: Bearer <YOUR_VAPI_API_KEY>" \
     -H "Content-Type: application/json" \
     -d @agent/vapi_config.json
   ```
3. Update the custom headers in the imported tools to use your production webhook secret (`X-Vapi-Secret`).

---

## 5. Live Call Testing
1. Buy or route a phone number inside the Vapi Dashboard (under **Numbers**).
2. Associate the number with your newly created **MediFlow AI Receptionist** assistant.
3. Call the number and test:
   - *"I'd like to book a cardiologist appointment with Dr. Suresh Rao tomorrow morning."*
   - *"Can you change my booking?"*
   - *"Can you give me medical advice?"* (Verify deflection logic).
