import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.models.doctor import Doctor
from app.models.availability import Availability
from app.models.slot import Slot

def generate_slots_for_doctor(session: Session, doctor_id: uuid.UUID, start_date: date | None = None, days: int | None = None):
    """
    Generate slots for a specific doctor over the next N days starting from start_date (inclusive).
    Naively schedules slots according to doctor's availability windows.
    Uses PostgreSQL ON CONFLICT DO NOTHING to ensure idempotency.
    """
    settings = get_settings()
    if days is None:
        days = settings.slot_generation_days
        
    tz = ZoneInfo(settings.timezone)
    
    if start_date is None:
        start_date = datetime.now(tz).date()
        
    # Fetch doctor availability windows
    availabilities = session.query(Availability).filter(Availability.doctor_id == doctor_id).all()
    if not availabilities:
        return 0
        
    slots_to_insert = []
    
    for offset in range(days):
        target_date = start_date + timedelta(days=offset)
        weekday = target_date.weekday() # Monday=0, Sunday=6
        
        # Find availability windows matching this weekday
        matching_windows = [a for a in availabilities if a.day_of_week == weekday]
        
        for win in matching_windows:
            duration = win.slot_duration
            
            # Start loop with window start_time
            current_time = win.start_time
            
            # We convert end_time into a timedelta from midnight for easy comparison
            end_delta = timedelta(hours=win.end_time.hour, minutes=win.end_time.minute)
            
            while True:
                current_delta = timedelta(hours=current_time.hour, minutes=current_time.minute)
                next_delta = current_delta + timedelta(minutes=duration)
                
                # Check if this slot fits within the availability window
                if next_delta > end_delta:
                    break
                    
                # Construct local datetimes
                local_start = datetime.combine(target_date, current_time, tzinfo=tz)
                local_end = local_start + timedelta(minutes=duration)
                
                # Convert to UTC
                start_utc = local_start.astimezone(timezone.utc)
                end_utc = local_end.astimezone(timezone.utc)
                
                slots_to_insert.append({
                    "doctor_id": doctor_id,
                    "availability_id": win.id,
                    "slot_start": start_utc,
                    "slot_end": end_utc,
                    "is_available": True
                })
                
                # Advance current_time
                next_time_dt = datetime.combine(target_date, current_time) + timedelta(minutes=duration)
                current_time = next_time_dt.time()
                
    if not slots_to_insert:
        return 0
        
    # Execute batch insert with ON CONFLICT DO NOTHING
    # PostgreSQL dialect required
    inserted_count = 0
    # Batch execute in chunks of 500
    chunk_size = 500
    for i in range(0, len(slots_to_insert), chunk_size):
        chunk = slots_to_insert[i:i+chunk_size]
        stmt = insert(Slot).values(chunk)
        stmt = stmt.on_conflict_do_nothing(index_elements=["doctor_id", "slot_start"])
        res = session.execute(stmt)
        inserted_count += res.rowcount
        
    session.commit()
    return inserted_count


def generate_all_slots(session: Session, start_date: date | None = None, days: int | None = None):
    """
    Generate slots for all active doctors in the database.
    """
    doctors = session.query(Doctor).all()
    total_slots = 0
    for doc in doctors:
        count = generate_slots_for_doctor(session, doc.id, start_date, days)
        total_slots += count
    return total_slots
