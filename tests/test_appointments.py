import pytest
import os
import sys
import threading
from datetime import datetime, time, timedelta, timezone
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(__file__))
try:
    from conftest import requires_db
except ImportError:
    import pytest
    requires_db = pytest.mark.skip(reason="conftest not importable")

import uuid
from sqlalchemy import text

from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.availability import Availability
from app.models.slot import Slot

from app.services.appointment_engine import (
    book_appointment,
    reschedule_appointment,
    cancel_appointment,
    SlotNotFoundError,
    SlotUnavailableError,
    PatientPhoneMismatchError,
    AppointmentStatusError,
)

@requires_db
class TestAppointmentEngine:
    """Validate transactional booking, rescheduling, cancellations, and concurrent locking."""

    def _setup_entities(self, session):
        clinic = Clinic(
            name="Apollo Test Hospital",
            address="123 Test St",
            city="Bengaluru",
            state="Karnataka",
            phone="+910000000000",
            website_url="https://example.com",
            source_url="https://example.com"
        )
        session.add(clinic)
        session.flush()

        doc = Doctor(
            clinic_id=clinic.id,
            name="Dr. Sarah Thomas",
            specialty="Orthopedics",
            department="Orthopedics",
            qualifications="MBBS, MS",
            source_url="https://example.com"
        )
        session.add(doc)
        session.flush()

        avail = Availability(
            doctor_id=doc.id,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(10, 0),
            slot_duration=30,
            source_url="https://example.com"
        )
        session.add(avail)
        session.flush()

        # Create two slots
        slot1 = Slot(
            doctor_id=doc.id,
            availability_id=avail.id,
            slot_start=datetime.now(timezone.utc) + timedelta(days=1),
            slot_end=datetime.now(timezone.utc) + timedelta(days=1, minutes=30),
            is_available=True
        )
        slot2 = Slot(
            doctor_id=doc.id,
            availability_id=avail.id,
            slot_start=datetime.now(timezone.utc) + timedelta(days=1, minutes=30),
            slot_end=datetime.now(timezone.utc) + timedelta(days=1, hours=1),
            is_available=True
        )
        session.add(slot1)
        session.add(slot2)
        session.flush()

        return clinic, doc, slot1, slot2

    def test_book_appointment_success(self, db_session):
        """Standard booking scenario."""
        _, _, slot1, _ = self._setup_entities(db_session)
        
        app = book_appointment(
            db_session,
            slot_id=slot1.id,
            patient_name="Rahul Verma",
            patient_phone="+919999999999",
            reason="Knee pain",
            call_id="call-12345"
        )
        
        assert app.id is not None
        assert app.patient_name == "Rahul Verma"
        assert app.patient_phone == "+919999999999"
        assert app.status == "confirmed"
        assert app.call_id == "call-12345"
        
        # Verify slot state
        assert not slot1.is_available

    def test_book_appointment_slot_not_found(self, db_session):
        """Booking a non-existent slot ID should raise SlotNotFoundError."""
        with pytest.raises(SlotNotFoundError):
            book_appointment(
                db_session,
                slot_id=uuid.uuid4(), # random UUID-like dummy
                patient_name="John Doe",
                patient_phone="+1234567890"
            )

    def test_book_appointment_already_booked(self, db_session):
        """Booking an already booked slot should raise SlotUnavailableError."""
        _, _, slot1, _ = self._setup_entities(db_session)
        slot1.is_available = False
        db_session.flush()

        with pytest.raises(SlotUnavailableError):
            book_appointment(
                db_session,
                slot_id=slot1.id,
                patient_name="Second Patient",
                patient_phone="+910000000000"
            )

    def test_reschedule_success(self, db_session):
        """Rescheduling frees the old slot, schedules the new, and creates a new appointment record."""
        _, _, slot1, slot2 = self._setup_entities(db_session)
        
        # Book original
        app1 = book_appointment(db_session, slot1.id, "Rahul Verma", "+919999999999")
        
        # Reschedule to slot2
        app2 = reschedule_appointment(
            db_session,
            appointment_id=app1.id,
            new_slot_id=slot2.id,
            patient_phone="+919999999999"
        )
        
        assert app2.id != app1.id
        assert app2.status == "confirmed"
        assert app2.original_slot_id == slot1.id
        
        # Verify old appointment state
        db_session.refresh(app1)
        assert app1.status == "rescheduled"
        assert app1.rescheduled_at is not None
        
        # Verify slot states
        assert slot1.is_available, "Old slot should be freed"
        assert not slot2.is_available, "New slot should be locked"

    def test_reschedule_validation_mismatches(self, db_session):
        """Rescheduling fails if phone validation fails or if original appointment is cancelled."""
        _, _, slot1, slot2 = self._setup_entities(db_session)
        app = book_appointment(db_session, slot1.id, "Rahul Verma", "+919999999999")
        
        # Test phone mismatch
        with pytest.raises(PatientPhoneMismatchError):
            reschedule_appointment(db_session, app.id, slot2.id, "+911111111111")
            
        # Test status constraint (cancel first)
        cancel_appointment(db_session, app.id, "+919999999999")
        with pytest.raises(AppointmentStatusError):
            reschedule_appointment(db_session, app.id, slot2.id, "+919999999999")

    def test_cancel_success(self, db_session):
        """Cancelling marks the appointment as cancelled and frees the slot."""
        _, _, slot1, _ = self._setup_entities(db_session)
        app = book_appointment(db_session, slot1.id, "Rahul Verma", "+919999999999")
        
        cancelled_app = cancel_appointment(
            db_session,
            appointment_id=app.id,
            patient_phone="+919999999999",
            cancellation_reason="Got busy"
        )
        
        assert cancelled_app.status == "cancelled"
        assert cancelled_app.cancellation_reason == "Got busy"
        assert cancelled_app.cancelled_at is not None
        
        # Verify slot freed
        assert slot1.is_available

    def test_cancel_phone_validation(self, db_session):
        """Cannot cancel with a mismatched phone number."""
        _, _, slot1, _ = self._setup_entities(db_session)
        app = book_appointment(db_session, slot1.id, "Rahul Verma", "+919999999999")
        
        with pytest.raises(PatientPhoneMismatchError):
            cancel_appointment(db_session, app.id, "+911111111111")

    def test_booking_concurrency_lock(self, test_engine):
        """
        Concurrency verification test.
        Fires two concurrent threads attempting to book the exact same slot.
        Asserts that exactly one succeeds and one raises SlotUnavailableError.
        """
        SessionLocal = sessionmaker(bind=test_engine)
        setup_session = SessionLocal()
        
        try:
            clinic, doc, slot1, slot2 = self._setup_entities(setup_session)
            slot_id = slot1.id
            setup_session.commit()
        finally:
            setup_session.close()
            
        results = []
        
        def worker(patient_name, phone):
            session = SessionLocal()
            try:
                app = book_appointment(session, slot_id, patient_name, phone)
                results.append(("success", app.id))
            except Exception as e:
                results.append(("error", type(e).__name__))
            finally:
                session.close()

        t1 = threading.Thread(target=worker, args=("Patient A", "+918888888888"))
        t2 = threading.Thread(target=worker, args=("Patient B", "+917777777777"))
        
        # Start both threads concurrently
        t1.start()
        t2.start()
        
        # Wait for both to finish
        t1.join()
        t2.join()
        
        # Cleanup database manually
        cleanup_session = SessionLocal()
        try:
            cleanup_session.execute(text("DELETE FROM appointments WHERE slot_id IN (SELECT id FROM slots WHERE doctor_id IN (SELECT id FROM doctors WHERE name = 'Dr. Sarah Thomas'))"))
            cleanup_session.execute(text("DELETE FROM slots WHERE doctor_id IN (SELECT id FROM doctors WHERE name = 'Dr. Sarah Thomas')"))
            cleanup_session.execute(text("DELETE FROM availability WHERE doctor_id IN (SELECT id FROM doctors WHERE name = 'Dr. Sarah Thomas')"))
            cleanup_session.execute(text("DELETE FROM doctors WHERE name = 'Dr. Sarah Thomas'"))
            cleanup_session.execute(text("DELETE FROM clinics WHERE name = 'Apollo Test Hospital'"))
            cleanup_session.commit()
        except Exception:
            cleanup_session.rollback()
            raise
        finally:
            cleanup_session.close()
            
        # We expect exactly one success and one SlotUnavailableError
        successes = [r for r in results if r[0] == "success"]
        errors = [r for r in results if r[0] == "error" and r[1] == "SlotUnavailableError"]
        
        assert len(successes) == 1, f"Expected 1 success, got {len(successes)}. Results: {results}"
        assert len(errors) == 1, f"Expected 1 SlotUnavailableError, got {len(errors)}. Results: {results}"
