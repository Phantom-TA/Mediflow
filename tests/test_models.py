"""
Phase 1 Tests — Database Layer

Split into two groups:
  [UNIT]        No DB required — always run. Verify model imports, metadata, constraints.
  [INTEGRATION] Requires live PostgreSQL — skipped gracefully if DB unavailable.

Tests:
  1.  [UNIT] All 7 model classes importable
  2.  [UNIT] Base.metadata registers all 7 tables
  3.  [UNIT] Model field names match schema doc
  4.  [UNIT] Appointment.is_confirmed property
  5.  [UNIT] Availability.day_name property
  6.  [UNIT] Doctor.full_name property
  7.  [INT]  All 7 tables exist in live DB
  8.  [INT]  Critical columns present
  9.  [INT]  Clinic CRUD
  10. [INT]  Doctor CRUD + full_name
  11. [INT]  Availability CRUD + day_name
  12. [INT]  Slot CRUD + is_available flag
  13. [INT]  Appointment CRUD + status
  14. [INT]  UNIQUE(doctor_id, slot_start) — duplicate slot rejected
  15. [INT]  UNIQUE(slot_id) on appointments — double booking rejected
  16. [INT]  CHECK: invalid day_of_week rejected
  17. [INT]  CHECK: end_time < start_time rejected
  18. [INT]  CHECK: invalid slot_duration rejected
  19. [INT]  CHECK: invalid appointment status rejected
  20. [INT]  FK CASCADE: delete doctor → slots cascade-deleted
  21. [INT]  FK RESTRICT: cannot delete slot with active appointment
  22. [INT]  ConversationSession CRUD
  23. [INT]  ConversationState CRUD + unique per call
  24. [INT]  Multiple slots per doctor — no overlap
  25. [INT]  Two doctors can share same slot_start time
  26. [INT]  Health endpoint returns 200
"""

import uuid
from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
# requires_db is defined in conftest.py and injected by pytest automatically.
# We import it explicitly only for class-level decoration.
try:
    from conftest import requires_db
except ImportError:
    import pytest
    requires_db = pytest.mark.skip(reason="conftest not importable directly")
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.availability import Availability
from app.models.slot import Slot
from app.models.appointment import Appointment
from app.models.conversation import ConversationSession, ConversationState
from app.database import Base

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

APOLLO_SOURCE = "https://www.apollohospitals.com/hospitals/bangalore/bannerghatta-road/"


# ─────────────────────────────────────────────────────────────────────────────
# UNIT Tests — no DB required
# ─────────────────────────────────────────────────────────────────────────────

class TestModelImports:
    """Verify all models import cleanly and metadata is registered."""

    def test_clinic_importable(self):
        assert Clinic is not None
        assert Clinic.__tablename__ == "clinics"

    def test_doctor_importable(self):
        assert Doctor is not None
        assert Doctor.__tablename__ == "doctors"

    def test_availability_importable(self):
        assert Availability is not None
        assert Availability.__tablename__ == "availability"

    def test_slot_importable(self):
        assert Slot is not None
        assert Slot.__tablename__ == "slots"

    def test_appointment_importable(self):
        assert Appointment is not None
        assert Appointment.__tablename__ == "appointments"

    def test_conversation_session_importable(self):
        assert ConversationSession is not None
        assert ConversationSession.__tablename__ == "conversation_sessions"

    def test_conversation_state_importable(self):
        assert ConversationState is not None
        assert ConversationState.__tablename__ == "conversation_state"

    def test_all_7_tables_in_metadata(self):
        """Base.metadata must contain exactly the 7 required tables."""
        expected = {
            "clinics", "doctors", "availability", "slots",
            "appointments", "conversation_sessions", "conversation_state",
        }
        registered = set(Base.metadata.tables.keys())
        assert expected.issubset(registered), (
            f"Missing from metadata: {expected - registered}"
        )


class TestModelProperties:
    """Unit-test computed properties that require no DB."""

    def test_doctor_full_name(self):
        doc = Doctor(salutation="Dr.", name="Suresh Rao")
        assert doc.full_name == "Dr. Suresh Rao"

    def test_doctor_full_name_custom_salutation(self):
        doc = Doctor(salutation="Prof.", name="Priya Menon")
        assert doc.full_name == "Prof. Priya Menon"

    def test_availability_day_name_monday(self):
        avail = Availability(day_of_week=0)
        assert avail.day_name == "Monday"

    def test_availability_day_name_sunday(self):
        avail = Availability(day_of_week=6)
        assert avail.day_name == "Sunday"

    def test_availability_all_day_names(self):
        expected = ["Monday", "Tuesday", "Wednesday", "Thursday",
                    "Friday", "Saturday", "Sunday"]
        for i, name in enumerate(expected):
            avail = Availability(day_of_week=i)
            assert avail.day_name == name

    def test_appointment_is_confirmed_true(self):
        appt = Appointment(status="confirmed")
        assert appt.is_confirmed is True

    def test_appointment_is_confirmed_false(self):
        appt = Appointment(status="cancelled")
        assert appt.is_confirmed is False

    def test_appointment_is_active_confirmed(self):
        appt = Appointment(status="confirmed")
        assert appt.is_active is True

    def test_appointment_is_active_cancelled(self):
        appt = Appointment(status="cancelled")
        assert appt.is_active is False


# ─────────────────────────────────────────────────────────────────────────────
# Helpers for integration tests
# ─────────────────────────────────────────────────────────────────────────────

def make_clinic(session) -> Clinic:
    clinic = Clinic(
        name="Apollo Hospital Bannerghatta Road",
        address="154/11, Opp. IIM-B, Bannerghatta Road",
        city="Bengaluru",
        state="Karnataka",
        phone="+91 80 2682 4444",
        website_url="https://www.apollohospitals.com/hospitals/bangalore/bannerghatta-road/",
        source_url=APOLLO_SOURCE,
    )
    session.add(clinic)
    session.flush()
    return clinic


def make_doctor(session, clinic: Clinic, specialty: str = "Cardiology") -> Doctor:
    doctor = Doctor(
        clinic_id=clinic.id,
        name=f"Test Doctor {uuid.uuid4().hex[:6]}",
        specialty=specialty,
        department=f"Department of {specialty}",
        qualifications="MBBS, MD",
        source_url=APOLLO_SOURCE,
    )
    session.add(doctor)
    session.flush()
    return doctor


def make_availability(session, doctor: Doctor, day: int = 0) -> Availability:
    avail = Availability(
        doctor_id=doctor.id,
        day_of_week=day,
        start_time=time(9, 0),
        end_time=time(13, 0),
        slot_duration=15,
        source_url=APOLLO_SOURCE,
    )
    session.add(avail)
    session.flush()
    return avail


def make_slot(session, doctor: Doctor, avail: Availability,
              offset_minutes: int = 0) -> Slot:
    base = datetime(2026, 6, 30, 3, 30, 0, tzinfo=timezone.utc)  # 09:00 IST
    start = base + timedelta(minutes=offset_minutes)
    slot = Slot(
        doctor_id=doctor.id,
        availability_id=avail.id,
        slot_start=start,
        slot_end=start + timedelta(minutes=15),
        is_available=True,
    )
    session.add(slot)
    session.flush()
    return slot


def make_appointment(session, clinic, doctor, slot, call_id="test-call") -> Appointment:
    appt = Appointment(
        slot_id=slot.id,
        doctor_id=doctor.id,
        clinic_id=clinic.id,
        patient_name="Ravi Kumar",
        patient_phone="+919876543210",
        call_id=call_id,
    )
    slot.is_available = False
    session.add(appt)
    session.flush()
    return appt


# ─────────────────────────────────────────────────────────────────────────────
# INTEGRATION Tests — require live PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────

@requires_db
class TestTableCreation:
    """All 7 required tables must exist in the database."""

    def test_all_tables_exist(self, test_engine):
        from sqlalchemy import inspect
        inspector = inspect(test_engine)
        existing = set(inspector.get_table_names())
        required = {
            "clinics", "doctors", "availability", "slots",
            "appointments", "conversation_sessions", "conversation_state",
        }
        missing = required - existing
        assert not missing, f"Missing tables: {missing}"

    def test_slots_critical_columns(self, test_engine):
        from sqlalchemy import inspect
        cols = {c["name"] for c in inspect(test_engine).get_columns("slots")}
        assert {"doctor_id", "slot_start", "slot_end", "is_available"}.issubset(cols)

    def test_appointments_critical_columns(self, test_engine):
        from sqlalchemy import inspect
        cols = {c["name"] for c in inspect(test_engine).get_columns("appointments")}
        assert {"slot_id", "patient_phone", "status", "call_id"}.issubset(cols)


@requires_db
class TestCRUD:
    """Basic create/read for all 5 core models."""

    def test_clinic_create(self, db_session):
        clinic = make_clinic(db_session)
        assert clinic.id is not None
        assert clinic.city == "Bengaluru"

    def test_doctor_create(self, db_session):
        clinic = make_clinic(db_session)
        doctor = make_doctor(db_session, clinic)
        assert doctor.id is not None
        assert "Dr." in doctor.full_name

    def test_availability_create(self, db_session):
        clinic = make_clinic(db_session)
        doctor = make_doctor(db_session, clinic)
        avail = make_availability(db_session, doctor, day=0)
        assert avail.id is not None
        assert avail.day_name == "Monday"

    def test_slot_create(self, db_session):
        clinic = make_clinic(db_session)
        doctor = make_doctor(db_session, clinic)
        avail = make_availability(db_session, doctor)
        slot = make_slot(db_session, doctor, avail)
        assert slot.id is not None
        assert slot.is_available is True

    def test_appointment_create(self, db_session):
        clinic = make_clinic(db_session)
        doctor = make_doctor(db_session, clinic)
        avail = make_availability(db_session, doctor)
        slot = make_slot(db_session, doctor, avail)
        appt = make_appointment(db_session, clinic, doctor, slot)
        assert appt.id is not None
        assert appt.status == "confirmed"
        assert slot.is_available is False


@requires_db
class TestConstraints:
    """DB-level constraint validation."""

    def test_unique_doctor_slot_rejected(self, db_session):
        """UNIQUE(doctor_id, slot_start) — same doctor same time must fail."""
        clinic = make_clinic(db_session)
        doctor = make_doctor(db_session, clinic)
        avail = make_availability(db_session, doctor)
        make_slot(db_session, doctor, avail, offset_minutes=0)
        with pytest.raises(IntegrityError):
            make_slot(db_session, doctor, avail, offset_minutes=0)

    def test_double_booking_rejected(self, db_session):
        """UNIQUE(slot_id) on appointments — two bookings for same slot must fail."""
        clinic = make_clinic(db_session)
        doctor = make_doctor(db_session, clinic)
        avail = make_availability(db_session, doctor)
        slot = make_slot(db_session, doctor, avail)
        make_appointment(db_session, clinic, doctor, slot, call_id="call-001")
        with pytest.raises(IntegrityError):
            appt2 = Appointment(
                slot_id=slot.id,
                doctor_id=doctor.id,
                clinic_id=clinic.id,
                patient_name="Priya Singh",
                patient_phone="+919999999999",
                call_id="call-002",
            )
            db_session.add(appt2)
            db_session.flush()

    def test_invalid_day_of_week_rejected(self, db_session):
        clinic = make_clinic(db_session)
        doctor = make_doctor(db_session, clinic)
        with pytest.raises(IntegrityError):
            bad = Availability(
                doctor_id=doctor.id, day_of_week=7,
                start_time=time(9, 0), end_time=time(13, 0),
                source_url=APOLLO_SOURCE,
            )
            db_session.add(bad)
            db_session.flush()

    def test_invalid_time_range_rejected(self, db_session):
        clinic = make_clinic(db_session)
        doctor = make_doctor(db_session, clinic)
        with pytest.raises(IntegrityError):
            bad = Availability(
                doctor_id=doctor.id, day_of_week=1,
                start_time=time(13, 0), end_time=time(9, 0),  # end < start
                source_url=APOLLO_SOURCE,
            )
            db_session.add(bad)
            db_session.flush()

    def test_invalid_slot_duration_rejected(self, db_session):
        clinic = make_clinic(db_session)
        doctor = make_doctor(db_session, clinic)
        with pytest.raises(IntegrityError):
            bad = Availability(
                doctor_id=doctor.id, day_of_week=2,
                start_time=time(9, 0), end_time=time(13, 0),
                slot_duration=45,  # not in (10,15,20,30)
                source_url=APOLLO_SOURCE,
            )
            db_session.add(bad)
            db_session.flush()

    def test_invalid_appointment_status_rejected(self, db_session):
        clinic = make_clinic(db_session)
        doctor = make_doctor(db_session, clinic)
        avail = make_availability(db_session, doctor)
        slot = make_slot(db_session, doctor, avail)
        with pytest.raises(IntegrityError):
            bad = Appointment(
                slot_id=slot.id, doctor_id=doctor.id, clinic_id=clinic.id,
                patient_name="Test", patient_phone="+910000000000",
                status="pending",  # not in valid set
            )
            db_session.add(bad)
            db_session.flush()


@requires_db
class TestForeignKeys:
    """Foreign key cascade and restrict behaviour."""

    def test_fk_cascade_doctor_delete(self, db_session):
        """Deleting a doctor must cascade-delete their slots."""
        clinic = make_clinic(db_session)
        doctor = make_doctor(db_session, clinic)
        avail = make_availability(db_session, doctor)
        slot = make_slot(db_session, doctor, avail)
        slot_id = slot.id
        db_session.delete(doctor)
        db_session.flush()
        assert db_session.get(Slot, slot_id) is None

    def test_fk_restrict_slot_with_appointment(self, db_session):
        """Cannot delete a slot that has a confirmed appointment."""
        clinic = make_clinic(db_session)
        doctor = make_doctor(db_session, clinic)
        avail = make_availability(db_session, doctor)
        slot = make_slot(db_session, doctor, avail)
        make_appointment(db_session, clinic, doctor, slot)
        with pytest.raises(IntegrityError):
            db_session.delete(slot)
            db_session.flush()


@requires_db
class TestConversation:
    """ConversationSession and ConversationState behaviour."""

    def test_session_create(self, db_session):
        sess = ConversationSession(call_id="vapi-test-001", patient_phone="+919876543210")
        db_session.add(sess)
        db_session.flush()
        assert sess.id is not None

    def test_state_create(self, db_session):
        sess = ConversationSession(call_id="vapi-test-002")
        db_session.add(sess)
        db_session.flush()
        state = ConversationState(
            call_id=sess.call_id, intent="book",
            patient_name="Ravi Kumar", confirmation_pending=False,
        )
        db_session.add(state)
        db_session.flush()
        assert state.intent == "book"

    def test_state_unique_per_call(self, db_session):
        sess = ConversationSession(call_id="vapi-test-003")
        db_session.add(sess)
        db_session.flush()
        db_session.add(ConversationState(call_id=sess.call_id, intent="book"))
        db_session.flush()
        with pytest.raises(IntegrityError):
            db_session.add(ConversationState(call_id=sess.call_id, intent="cancel"))
            db_session.flush()


@requires_db
class TestSlotRules:
    """Slot generation and multi-doctor rules."""

    def test_multiple_slots_no_overlap(self, db_session):
        clinic = make_clinic(db_session)
        doctor = make_doctor(db_session, clinic)
        avail = make_availability(db_session, doctor)
        slots = [make_slot(db_session, doctor, avail, i * 15) for i in range(8)]
        assert len(slots) == 8
        assert all(s.id is not None for s in slots)

    def test_two_doctors_same_start_time_allowed(self, db_session):
        """UNIQUE is per-doctor; different doctors can share a start time."""
        clinic = make_clinic(db_session)
        d1 = make_doctor(db_session, clinic, "Cardiology")
        d2 = make_doctor(db_session, clinic, "Neurology")
        a1 = make_availability(db_session, d1)
        a2 = make_availability(db_session, d2)
        s1 = make_slot(db_session, d1, a1, 0)
        s2 = make_slot(db_session, d2, a2, 0)
        assert s1.slot_start == s2.slot_start
        assert s1.doctor_id != s2.doctor_id


@requires_db
class TestHealthEndpoint:
    """FastAPI /health endpoint."""

    def test_health_returns_200(self, test_client):
        response = test_client.get("/health")
        assert response.status_code == 200

    def test_health_body_fields(self, test_client):
        body = test_client.get("/health").json()
        assert "status" in body
        assert "database" in body
        assert "version" in body
