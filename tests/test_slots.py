import pytest
import os
import sys
from datetime import date, datetime, time, timezone

sys.path.insert(0, os.path.dirname(__file__))
try:
    from conftest import requires_db
except ImportError:
    import pytest
    requires_db = pytest.mark.skip(reason="conftest not importable directly")

from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.availability import Availability
from app.models.slot import Slot
from app.services.slot_engine import generate_slots_for_doctor, generate_all_slots

# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests — require live PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────

@requires_db
class TestSlotEngine:
    """Validate weekly scheduling, timezone conversion, boundary rules, and idempotency."""

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
            name="Dr. Raj Prasad",
            specialty="Cardiology",
            department="Cardiology",
            qualifications="MBBS, MD",
            source_url="https://example.com"
        )
        session.add(doc)
        session.flush()
        return clinic, doc

    def test_basic_slot_generation(self, db_session):
        """Create standard availability and verify 15-minute slot generation."""
        _, doc = self._setup_entities(db_session)
        
        # Tuesday availability: 09:00 - 10:00 (15 min slots)
        avail = Availability(
            doctor_id=doc.id,
            day_of_week=1, # Tuesday
            start_time=time(9, 0),
            end_time=time(10, 0),
            slot_duration=15,
            source_url="https://example.com"
        )
        db_session.add(avail)
        db_session.flush()
        
        # Target a specific Tuesday: 2026-06-30
        target_date = date(2026, 6, 30)
        
        count = generate_slots_for_doctor(db_session, doc.id, start_date=target_date, days=1)
        assert count == 4, f"Expected 4 slots for 1 hour window with 15 min slots, got {count}"
        
        # Verify slots exist and are correct
        slots = db_session.query(Slot).filter(Slot.doctor_id == doc.id).order_by(Slot.slot_start).all()
        assert len(slots) == 4
        
        # Verify timezone conversion: 09:00 IST is 03:30 UTC
        assert slots[0].slot_start == datetime(2026, 6, 30, 3, 30, tzinfo=timezone.utc)
        assert slots[0].slot_end == datetime(2026, 6, 30, 3, 45, tzinfo=timezone.utc)
        
        assert slots[3].slot_start == datetime(2026, 6, 30, 4, 15, tzinfo=timezone.utc)
        assert slots[3].slot_end == datetime(2026, 6, 30, 4, 30, tzinfo=timezone.utc)

    def test_slot_generation_boundary_spillover(self, db_session):
        """Ensure no slot is generated if it spills past the end_time boundary."""
        _, doc = self._setup_entities(db_session)
        
        # Tuesday availability: 09:00 - 09:20 (15 min slots)
        # Should generate only 1 slot: 09:00-09:15.
        # The remaining 5 minutes (09:15-09:20) cannot form a full slot.
        avail = Availability(
            doctor_id=doc.id,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(9, 20),
            slot_duration=15,
            source_url="https://example.com"
        )
        db_session.add(avail)
        db_session.flush()
        
        target_date = date(2026, 6, 30)
        count = generate_slots_for_doctor(db_session, doc.id, start_date=target_date, days=1)
        assert count == 1
        
        slots = db_session.query(Slot).filter(Slot.doctor_id == doc.id).all()
        assert len(slots) == 1
        assert slots[0].slot_start == datetime(2026, 6, 30, 3, 30, tzinfo=timezone.utc)
        assert slots[0].slot_end == datetime(2026, 6, 30, 3, 45, tzinfo=timezone.utc)

    def test_slot_generation_idempotency(self, db_session):
        """Re-running the slot generator must return 0 new slots and preserve existing slots."""
        _, doc = self._setup_entities(db_session)
        
        avail = Availability(
            doctor_id=doc.id,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(9, 30),
            slot_duration=15,
            source_url="https://example.com"
        )
        db_session.add(avail)
        db_session.flush()
        
        target_date = date(2026, 6, 30)
        
        # First run
        c1 = generate_slots_for_doctor(db_session, doc.id, start_date=target_date, days=1)
        assert c1 == 2
        
        # Second run
        c2 = generate_slots_for_doctor(db_session, doc.id, start_date=target_date, days=1)
        assert c2 == 0, "Idempotency failed: generated new slots on duplicate run"
        
        # Confirm no duplicate database entries exist
        slots = db_session.query(Slot).filter(Slot.doctor_id == doc.id).all()
        assert len(slots) == 2

    def test_generate_all_slots_multi_doctor(self, db_session):
        """Verify that generate_all_slots targets all doctors in database."""
        clinic, d1 = self._setup_entities(db_session)
        
        d2 = Doctor(
            clinic_id=clinic.id,
            name="Dr. Sonia Mehta",
            specialty="Pediatrics",
            department="Pediatrics",
            qualifications="MBBS, MD",
            source_url="https://example.com"
        )
        db_session.add(d2)
        db_session.flush()
        
        # d1 availability: Tuesday 09:00 - 09:30 (15 min)
        a1 = Availability(
            doctor_id=d1.id,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(9, 30),
            slot_duration=15,
            source_url="https://example.com"
        )
        db_session.add(a1)
        
        # d2 availability: Tuesday 14:00 - 14:45 (15 min)
        a2 = Availability(
            doctor_id=d2.id,
            day_of_week=1,
            start_time=time(14, 0),
            end_time=time(14, 45),
            slot_duration=15,
            source_url="https://example.com"
        )
        db_session.add(a2)
        db_session.flush()
        
        target_date = date(2026, 6, 30)
        total = generate_all_slots(db_session, start_date=target_date, days=1)
        assert total == 5 # 2 for d1 + 3 for d2
        
        # Check that d1 and d2 have their respective slots
        s1 = db_session.query(Slot).filter(Slot.doctor_id == d1.id).all()
        s2 = db_session.query(Slot).filter(Slot.doctor_id == d2.id).all()
        
        assert len(s1) == 2
        assert len(s2) == 3
