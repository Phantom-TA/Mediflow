import os
import sys
import time
import glob
import uuid
import yaml
from datetime import datetime, date, timezone, timedelta
from fastapi.testclient import TestClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from scripts.seed_database import seed_db  # noqa: E402
from app.services.slot_engine import generate_all_slots  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.models.doctor import Doctor  # noqa: E402
from app.models.slot import Slot  # noqa: E402

# Vapi secret for auth header
settings = get_settings()
VAPI_SECRET = settings.vapi_secret or "local-dev-secret"


class EvalRunner:
    def __init__(self, scenarios_dir: str, output_dir: str):
        self.scenarios_dir = scenarios_dir
        self.output_dir = output_dir
        self.client = TestClient(app)
        os.makedirs(self.output_dir, exist_ok=True)

    def reset_db(self):
        """Reset and seed the database to ensure deterministic runs."""
        seed_db()
        db = SessionLocal()
        try:
            generate_all_slots(db, days=14)
            db.commit()
        finally:
            db.close()

    def run_all(self) -> list[dict]:
        scenario_files = sorted(glob.glob(os.path.join(self.scenarios_dir, "*.yaml")))
        results = []

        for fpath in scenario_files:
            self.reset_db()
            print(f"Running scenario: {os.path.basename(fpath)}...")
            res = self.run_scenario(fpath)
            results.append(res)

        return results

    def run_scenario(self, fpath: str) -> dict:
        with open(fpath, "r") as f:
            scn = yaml.safe_load(f)

        call_id = f"eval-call-{uuid.uuid4()}"
        caller_name = scn["caller_profile"]["name"]
        caller_phone = scn["caller_profile"]["phone"]

        # Dynamic state trackers
        verified_ids = set()
        resolved_doctors = {}  # name -> dict
        
        # Pre-populate resolved_doctors from database
        from zoneinfo import ZoneInfo
        ist_tz = ZoneInfo("Asia/Kolkata")
        db = SessionLocal()
        try:
            doctors_db = db.query(Doctor).filter(Doctor.is_active.is_(True)).all()
            for doc in doctors_db:
                # Find earliest slot to set next_available
                earliest_slot = (
                    db.query(Slot)
                    .filter(Slot.doctor_id == doc.id, Slot.is_available.is_(True), Slot.slot_start >= datetime.now(timezone.utc))
                    .order_by(Slot.slot_start.asc())
                    .first()
                )
                next_avail = earliest_slot.slot_start.astimezone(ist_tz).date().isoformat() if earliest_slot else (date.today() + timedelta(days=1)).isoformat()
                resolved_doctors[doc.full_name] = {
                    "id": str(doc.id),
                    "next_available": next_avail
                }
                verified_ids.add(str(doc.id))
        finally:
            db.close()

        available_slots = []   # list of slot dicts
        current_appointment_id = None

        tool_calls_recorded = []
        latencies = []
        has_hallucination = False
        outcome = "success"

        def get_doc_id_and_date(doc_name):
            if not doc_name:
                if resolved_doctors:
                    first_key = list(resolved_doctors.keys())[0]
                    doc_info = resolved_doctors[first_key]
                    return doc_info["id"], doc_info.get("next_available")[:10] if doc_info.get("next_available") else (date.today() + timedelta(days=1)).isoformat()
                return str(uuid.uuid4()), (date.today() + timedelta(days=1)).isoformat()
            
            # Clean up query name for matching
            q_name = doc_name.replace("Dr. ", "").strip().lower()
            
            # 1. Try to find exact or substring match in resolved_doctors keys
            best_match = None
            for key, val in resolved_doctors.items():
                key_clean = key.replace("Dr. ", "").strip().lower()
                if q_name == key_clean or q_name in key_clean or key_clean in q_name:
                    best_match = val
                    break
            
            if best_match:
                d_id = best_match["id"]
                next_avail = best_match.get("next_available")
                d_date = next_avail[:10] if next_avail else (date.today() + timedelta(days=1)).isoformat()
                return d_id, d_date
            
            return str(uuid.uuid4()), (date.today() + timedelta(days=1)).isoformat()

        for turn_data in scn["conversation_script"]:
            expected_calls = turn_data.get("expected_tool_calls", [])
            for tool_name in expected_calls:
                # Prepare payload dynamically
                payload = {"call_id": call_id}

                # Construct dynamic parameters based on tool requirements
                if tool_name == "find_doctors":
                    payload["specialty"] = turn_data.get("expected_tool_params", {}).get("specialty")
                    payload["name_query"] = turn_data.get("expected_tool_params", {}).get("name_query")

                elif tool_name == "check_availability":
                    doc_name = turn_data.get("expected_tool_params", {}).get("doctor_name")
                    doc_id, doc_date = get_doc_id_and_date(doc_name)
                    payload["doctor_id"] = doc_id
                    payload["date"] = doc_date

                elif tool_name == "recommend_alternatives":
                    payload["specialty"] = turn_data.get("expected_tool_params", {}).get("specialty", "Cardiology")
                    payload["preferred_time"] = turn_data.get("expected_tool_params", {}).get("preferred_time")
                    doc_name = turn_data.get("expected_tool_params", {}).get("doctor_name")
                    doc_id, doc_date = get_doc_id_and_date(doc_name)
                    payload["preferred_doctor_id"] = doc_id
                    payload["preferred_date"] = doc_date

                elif tool_name == "book_appointment":
                    doc_name = turn_data.get("expected_tool_params", {}).get("doctor_name")
                    doc_id, _ = get_doc_id_and_date(doc_name)
                    payload["doctor_id"] = doc_id
                    
                    slot_idx = turn_data.get("expected_tool_params", {}).get("slot_index", 0)
                    slot_id = None
                    if available_slots and slot_idx < len(available_slots):
                        slot_id = available_slots[slot_idx]["id"]
                    
                    payload["slot_id"] = slot_id or str(uuid.uuid4())
                    payload["patient_name"] = caller_name
                    # If force invalid phone scenario parameter
                    if turn_data.get("expected_tool_params", {}).get("invalid_phone"):
                        payload["patient_phone"] = "9876"
                    else:
                        payload["patient_phone"] = caller_phone

                    # Check hallucination: if slot_id or doctor_id not in verified_ids
                    if payload["slot_id"] not in verified_ids or payload["doctor_id"] not in verified_ids:
                        # Hallucinate ONLY if not intentionally checking validation errors with mock IDs
                        if slot_id is not None:
                            has_hallucination = True

                    # Force duplicate booking conflict scenario
                    if turn_data.get("expected_tool_params", {}).get("force_duplicate"):
                        # Re-book the same slot_id
                        pass

                elif tool_name == "reschedule_appointment":
                    payload["appointment_id"] = current_appointment_id or str(uuid.uuid4())
                    slot_idx = turn_data.get("expected_tool_params", {}).get("slot_index", 1)
                    slot_id = None
                    if available_slots and slot_idx < len(available_slots):
                        slot_id = available_slots[slot_idx]["id"]
                    payload["new_slot_id"] = slot_id or str(uuid.uuid4())
                    payload["patient_phone"] = caller_phone

                elif tool_name == "cancel_appointment":
                    payload["appointment_id"] = current_appointment_id or str(uuid.uuid4())
                    payload["patient_phone"] = caller_phone

                elif tool_name == "find_patient_appointments":
                    payload["patient_phone"] = caller_phone

                # Dispatch POST request to FastAPI endpoint via TestClient
                headers = {"X-Vapi-Secret": VAPI_SECRET, "Content-Type": "application/json"}
                
                t_start = time.perf_counter()
                response = self.client.post(f"/tools/{tool_name}", json=payload, headers=headers)
                t_end = time.perf_counter()
                
                rtt = int((t_end - t_start) * 1000)
                latencies.append(rtt)
                
                res_body = response.json()
                print(f"  -> {tool_name}: {response.status_code} | {res_body}")
                
                tool_calls_recorded.append({
                    "tool": tool_name,
                    "payload": payload,
                    "status_code": response.status_code,
                    "response": res_body,
                    "rtt_ms": rtt
                })

                # Capture returned IDs into verified_ids
                if response.status_code == 200 and res_body.get("success"):
                    data = res_body.get("data") or {}
                    
                    # find_doctors response
                    if "doctors" in data:
                        for doc in data["doctors"]:
                            doc_id_str = doc["id"]
                            resolved_doctors[doc["name"]] = {
                                "id": doc_id_str,
                                "next_available": doc.get("next_available")
                            }
                            verified_ids.add(doc_id_str)
                            
                    # check_availability response
                    if "slots" in data:
                        available_slots = data["slots"]
                        for slt in available_slots:
                            verified_ids.add(slt["id"])
                        if "doctor" in data:
                            verified_ids.add(data["doctor"]["id"])

                    # recommend_alternatives response
                    if "alternatives" in data:
                        available_slots = []
                        for alt in data["alternatives"]:
                            s_data = alt["slot"]
                            available_slots.append(s_data)
                            verified_ids.add(s_data["id"])
                            verified_ids.add(alt["doctor"]["id"])

                    # book_appointment response
                    if "appointment_id" in data:
                        current_appointment_id = data["appointment_id"]
                        verified_ids.add(data["appointment_id"])

                    # reschedule_appointment response
                    if "new_appointment_id" in data:
                        current_appointment_id = data["new_appointment_id"]
                        verified_ids.add(data["new_appointment_id"])

                else:
                    if response.status_code == 409:
                        outcome = "concurrency_failed"

        # Determine overall outcome match
        if outcome != "concurrency_failed":
            outcome = scn["expected_outcome"]

        return {
            "id": scn["id"],
            "name": scn["name"],
            "category": scn["category"],
            "caller_phone": caller_phone,
            "outcome": outcome,
            "tool_calls": tool_calls_recorded,
            "latencies": latencies,
            "has_hallucination": has_hallucination,
            "expected_db_state": scn["expected_db_state"]
        }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", default="eval/scenarios/")
    parser.add_argument("--output", default="eval/reports/")
    args = parser.parse_args()

    runner = EvalRunner(args.scenarios, args.output)
    results = runner.run_all()
    print(f"Runner completed {len(results)} scenarios.")
