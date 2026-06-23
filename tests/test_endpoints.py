import pytest
import os
import sys
import json
from datetime import datetime, time, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
try:
    from conftest import requires_db
except ImportError:
    import pytest
    requires_db = pytest.mark.skip(reason="conftest not importable")

from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.availability import Availability
from app.models.slot import Slot
from app.models.appointment import Appointment
from app.config import get_settings


@requires_db
class TestFastAPIToolLayer:
    """Verify endpoint schemas, routers, security headers, and the Vapi unified webhook handler."""

    @pytest.fixture(autouse=True)
    def setup_headers(self):
        settings = get_settings()
        self.headers = {}
        if settings.vapi_secret:
            self.headers["X-Vapi-Secret"] = settings.vapi_secret

    def _setup_entities(self, session):
        clinic = Clinic(
            name="Apollo Web Hospital",
            address="456 Web Rd",
            city="Bengaluru",
            state="Karnataka",
            phone="+911111111111",
            website_url="https://example.com",
            source_url="https://example.com"
        )
        session.add(clinic)
        session.flush()

        doc = Doctor(
            clinic_id=clinic.id,
            name="Suresh Rao",
            specialty="Cardiology",
            department="Cardiology Department",
            qualifications="MBBS, MD, DM",
            experience_years=15,
            designation="Senior Consultant",
            source_url="https://example.com"
        )
        session.add(doc)
        session.flush()

        avail = Availability(
            doctor_id=doc.id,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(10, 0),
            slot_duration=15,
            source_url="https://example.com"
        )
        session.add(avail)
        session.flush()

        # Generate a slot for tomorrow
        slot_time = datetime.now(timezone.utc) + timedelta(days=1)
        # Ensure it matches the hour
        slot_time = slot_time.replace(hour=9, minute=0, second=0, microsecond=0)

        slot1 = Slot(
            doctor_id=doc.id,
            availability_id=avail.id,
            slot_start=slot_time,
            slot_end=slot_time + timedelta(minutes=15),
            is_available=True
        )
        slot2 = Slot(
            doctor_id=doc.id,
            availability_id=avail.id,
            slot_start=slot_time + timedelta(minutes=15),
            slot_end=slot_time + timedelta(minutes=30),
            is_available=True
        )
        session.add(slot1)
        session.add(slot2)
        session.flush()

        return clinic, doc, slot1, slot2

    def test_security_auth_check(self, test_client):
        settings = get_settings()
        if not settings.vapi_secret:
            pytest.skip("No vapi_secret configured, skipping security check.")

        # Test request without header returns 401
        res = test_client.post("/tools/find_doctors", json={"call_id": "1", "specialty": "Cardio"})
        assert res.status_code == 401
        assert res.json()["success"] is False

        # Test request with invalid header returns 401
        res = test_client.post(
            "/tools/find_doctors",
            json={"call_id": "1", "specialty": "Cardio"},
            headers={"X-Vapi-Secret": "wrong-secret"}
        )
        assert res.status_code == 401
        assert res.json()["success"] is False

    def test_find_doctors_endpoint(self, test_client, db_session):
        _, doc, _, _ = self._setup_entities(db_session)
        db_session.commit()

        # Test finding doctor by specialty
        payload = {
            "call_id": "test-call-1",
            "specialty": "Cardiology"
        }
        res = test_client.post("/tools/find_doctors", json=payload, headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert len(data["data"]["doctors"]) == 1
        assert data["data"]["doctors"][0]["name"] == "Dr. Suresh Rao"

    def test_check_availability_endpoint(self, test_client, db_session):
        _, doc, slot1, _ = self._setup_entities(db_session)
        db_session.commit()

        # Query slot date
        query_date = slot1.slot_start.date().isoformat()
        payload = {
            "call_id": "test-call-2",
            "doctor_id": str(doc.id),
            "date": query_date
        }
        res = test_client.post("/tools/check_availability", json=payload, headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert len(data["data"]["slots"]) > 0

    def test_book_appointment_endpoint(self, test_client, db_session):
        _, doc, slot1, _ = self._setup_entities(db_session)
        db_session.commit()

        payload = {
            "call_id": "test-call-3",
            "slot_id": str(slot1.id),
            "doctor_id": str(doc.id),
            "patient_name": "Kumar",
            "patient_phone": "+919876543210"
        }
        res = test_client.post("/tools/book_appointment", json=payload, headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["data"]["patient_name"] == "Kumar"
        assert "Appointment confirmed" in data["data"]["confirmation_message"]

    def test_reschedule_appointment_endpoint(self, test_client, db_session):
        _, doc, slot1, slot2 = self._setup_entities(db_session)
        # Create an existing appointment
        app = Appointment(
            slot_id=slot1.id,
            doctor_id=doc.id,
            clinic_id=doc.clinic_id,
            patient_name="Kumar",
            patient_phone="+919876543210",
            status="confirmed"
        )
        db_session.add(app)
        slot1.is_available = False
        db_session.commit()

        payload = {
            "call_id": "test-call-4",
            "appointment_id": str(app.id),
            "new_slot_id": str(slot2.id),
            "patient_phone": "+919876543210"
        }
        res = test_client.post("/tools/reschedule_appointment", json=payload, headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["data"]["new_appointment_id"] != str(app.id)

    def test_cancel_appointment_endpoint(self, test_client, db_session):
        _, doc, slot1, _ = self._setup_entities(db_session)
        app = Appointment(
            slot_id=slot1.id,
            doctor_id=doc.id,
            clinic_id=doc.clinic_id,
            patient_name="Kumar",
            patient_phone="+919876543210",
            status="confirmed"
        )
        db_session.add(app)
        slot1.is_available = False
        db_session.commit()

        payload = {
            "call_id": "test-call-5",
            "appointment_id": str(app.id),
            "patient_phone": "+919876543210",
            "reason": "Health got better"
        }
        res = test_client.post("/tools/cancel_appointment", json=payload, headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["data"]["status"] == "cancelled"

    def test_find_patient_appointments_endpoint(self, test_client, db_session):
        _, doc, slot1, _ = self._setup_entities(db_session)
        app = Appointment(
            slot_id=slot1.id,
            doctor_id=doc.id,
            clinic_id=doc.clinic_id,
            patient_name="Kumar",
            patient_phone="+919876543210",
            status="confirmed"
        )
        db_session.add(app)
        slot1.is_available = False
        db_session.commit()

        payload = {
            "call_id": "test-call-6",
            "patient_phone": "+919876543210"
        }
        res = test_client.post("/tools/find_patient_appointments", json=payload, headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert len(data["data"]["appointments"]) == 1

    def test_recommend_alternatives_endpoint(self, test_client, db_session):
        _, doc, slot1, _ = self._setup_entities(db_session)
        db_session.commit()

        payload = {
            "call_id": "test-call-7",
            "specialty": "Cardiology",
            "preferred_doctor_id": str(doc.id),
            "preferred_date": slot1.slot_start.date().isoformat()
        }
        res = test_client.post("/tools/recommend_alternatives", json=payload, headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert len(data["data"]["alternatives"]) > 0

    def test_validation_error_shape(self, test_client):
        # Fire a bad request missing required fields
        res = test_client.post("/tools/find_doctors", json={}, headers=self.headers)
        assert res.status_code == 422
        data = res.json()
        assert data["success"] is False
        assert data["error_code"] == "VALIDATION_ERROR"
        assert "Validation error" in data["error_message"]

    def test_vapi_unified_webhook(self, test_client, db_session):
        _, doc, slot1, _ = self._setup_entities(db_session)
        db_session.commit()

        # Build Vapi unified tool request structure
        payload = {
            "message": {
                "type": "tool-calls",
                "toolCallList": [
                    {
                        "id": "vapi-tc-1",
                        "type": "function",
                        "function": {
                            "name": "find_doctors",
                            "arguments": json.dumps({
                                "specialty": "Cardiology"
                            })
                        }
                    }
                ],
                "call": {
                    "id": "vapi-call-123",
                    "phoneNumber": "+919876543210"
                }
            }
        }

        res = test_client.post("/vapi/tool", json=payload, headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["toolCallId"] == "vapi-tc-1"
        
        # Result content is a serialized JSON string
        result_content = json.loads(data["results"][0]["result"])
        assert result_content["success"] is True
        assert len(result_content["data"]["doctors"]) == 1
