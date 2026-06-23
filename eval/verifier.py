import os
import sys
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database import SessionLocal  # noqa: E402
from app.models.appointment import Appointment  # noqa: E402


class EvalVerifier:
    def __init__(self):
        self.db = SessionLocal()

    def verify_scenario(self, res: dict) -> dict:
        expected = res.get("expected_db_state", {})
        assertions = []
        passed = True

        db = SessionLocal()
        try:
            # 1. Verify specific appointments expectations
            if "appointments" in expected:
                for exp_appt in expected["appointments"]:
                    patient_name = exp_appt.get("patient_name")
                    patient_phone = exp_appt.get("patient_phone")
                    status = exp_appt.get("status")
                    doctor_name = exp_appt.get("doctor_name")

                    query = db.query(Appointment)
                    if patient_phone:
                        query = query.filter(Appointment.patient_phone == patient_phone)
                    if patient_name:
                        query = query.filter(Appointment.patient_name == patient_name)
                    if status:
                        query = query.filter(Appointment.status == status)

                    records = query.all()
                    match_found = False

                    for record in records:
                        if doctor_name:
                            # Verify matching doctor name
                            if record.slot.doctor.full_name == doctor_name:
                                match_found = True
                                break
                        else:
                            match_found = True
                            break

                    assertions.append({
                        "type": "appointment_exists",
                        "expected": exp_appt,
                        "passed": match_found
                    })
                    if not match_found:
                        passed = False

            # 2. Verify exact appointment count
            if "appointments_count" in expected:
                cnt = db.query(Appointment).count()
                expected_cnt = expected["appointments_count"]
                match = cnt == expected_cnt
                assertions.append({
                    "type": "appointment_count",
                    "expected": expected_cnt,
                    "actual": cnt,
                    "passed": match
                })
                if not match:
                    passed = False
        finally:
            db.close()

        return {
            "id": res["id"],
            "name": res["name"],
            "passed": passed,
            "assertions": assertions
        }
