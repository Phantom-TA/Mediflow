import pytest
import os
import sys
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
from app.services.conflict_resolver import (
    resolve_specialties_and_departments,
    compute_alternative_slots,
)


@requires_db
class TestSchedulingIntelligence:
    """Validate fuzzy specialty resolution and heuristic alternative slot scoring/ranking."""

    def _setup_test_data(self, session):
        clinic = Clinic(
            name="Apollo Intelligence Care",
            address="123 Smart Way",
            city="Bengaluru",
            state="Karnataka",
            phone="+919999999999",
            website_url="https://example.com",
            source_url="https://example.com"
        )
        session.add(clinic)
        session.flush()

        # Doctor 1: Cardiologist
        doc_cardio = Doctor(
            clinic_id=clinic.id,
            name="Amit Shah",
            specialty="Cardiology",
            department="Cardiology Department",
            qualifications="MBBS, MD",
            experience_years=10,
            designation="Consultant",
            source_url="https://example.com"
        )
        # Doctor 2: Pediatrician
        doc_pediatric = Doctor(
            clinic_id=clinic.id,
            name="Sita Ram",
            specialty="Pediatrics & Neonatology",
            department="Pediatrics Department",
            qualifications="MBBS, DCH",
            experience_years=12,
            designation="Senior Consultant",
            source_url="https://example.com"
        )
        session.add(doc_cardio)
        session.add(doc_pediatric)
        session.flush()

        # Create availability records
        avail_cardio = Availability(
            doctor_id=doc_cardio.id,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(17, 0),
            slot_duration=15,
            source_url="https://example.com"
        )
        avail_pediatric = Availability(
            doctor_id=doc_pediatric.id,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(17, 0),
            slot_duration=15,
            source_url="https://example.com"
        )
        session.add(avail_cardio)
        session.add(avail_pediatric)
        session.flush()

        # Add availability and slots for both doctors
        now_utc = datetime.now(timezone.utc)
        tomorrow = now_utc + timedelta(days=1)
        day_after = now_utc + timedelta(days=2)

        # Tomorrow slot for Cardio
        slot_cardio_1 = Slot(
            doctor_id=doc_cardio.id,
            availability_id=avail_cardio.id,
            slot_start=tomorrow.replace(hour=10, minute=0, second=0, microsecond=0),
            slot_end=tomorrow.replace(hour=10, minute=15, second=0, microsecond=0),
            is_available=True
        )
        # Day after slot for Cardio (later time)
        slot_cardio_2 = Slot(
            doctor_id=doc_cardio.id,
            availability_id=avail_cardio.id,
            slot_start=day_after.replace(hour=14, minute=0, second=0, microsecond=0),
            slot_end=day_after.replace(hour=14, minute=15, second=0, microsecond=0),
            is_available=True
        )
        # Tomorrow slot for Pediatrician
        slot_pediatric_1 = Slot(
            doctor_id=doc_pediatric.id,
            availability_id=avail_pediatric.id,
            slot_start=tomorrow.replace(hour=10, minute=0, second=0, microsecond=0),
            slot_end=tomorrow.replace(hour=10, minute=15, second=0, microsecond=0),
            is_available=True
        )

        session.add(slot_cardio_1)
        session.add(slot_cardio_2)
        session.add(slot_pediatric_1)
        session.flush()

        return doc_cardio, doc_pediatric, slot_cardio_1, slot_cardio_2, slot_pediatric_1

    def test_specialty_alias_resolution(self, db_session):
        doc_cardio, doc_pediatric, _, _, _ = self._setup_test_data(db_session)
        db_session.commit()

        # 1. Test exact alias
        resolved = resolve_specialties_and_departments("heart", db_session)
        assert "Cardiology" in resolved or "Cardiology Department" in resolved

        # 2. Test exact spelling
        resolved = resolve_specialties_and_departments("pediatrics", db_session)
        assert "Pediatrics & Neonatology" in resolved

        # 3. Test spelling error / fuzzy match
        resolved = resolve_specialties_and_departments("cardology", db_session)
        assert "Cardiology" in resolved or "Cardiology Department" in resolved

        # 4. Test child alias
        resolved = resolve_specialties_and_departments("child", db_session)
        assert "Pediatrics & Neonatology" in resolved

    def test_heuristic_ranking_logic(self, db_session):
        doc_cardio, doc_pediatric, slot_cardio_1, slot_cardio_2, slot_pediatric_1 = self._setup_test_data(db_session)
        db_session.commit()

        preferred_date = slot_cardio_1.slot_start.date()

        # Query alternatives for Cardiology with preferred doctor Amit Shah at 10:00
        alternatives = compute_alternative_slots(
            db=db_session,
            specialty_query="heart",
            preferred_doctor_id=doc_cardio.id,
            preferred_date=preferred_date,
            preferred_time="10:00",
            max_results=5
        )

        # Should return slot_cardio_1 as rank 1 since it matches doctor, specialty, date and time perfectly
        assert len(alternatives) > 0
        score_1, slot_1, reason_1 = alternatives[0]
        assert slot_1.id == slot_cardio_1.id
        assert "Same doctor" in reason_1

        # Second alternative should be slot_cardio_2 (same doctor, but day after and different time)
        if len(alternatives) > 1:
            score_2, slot_2, reason_2 = alternatives[1]
            assert slot_2.id == slot_cardio_2.id
            assert score_1 > score_2
