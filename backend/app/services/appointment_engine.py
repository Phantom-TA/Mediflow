import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.models.slot import Slot
from app.models.appointment import Appointment

# ── Custom Exceptions ─────────────────────────────────────────────────────────

class SlotNotFoundError(ValueError):
    """Raised when the requested slot ID does not exist in the database."""
    pass

class SlotUnavailableError(ValueError):
    """Raised when the slot is already booked or locked by another process."""
    pass

class AppointmentNotFoundError(ValueError):
    """Raised when the requested appointment ID does not exist."""
    pass

class PatientPhoneMismatchError(ValueError):
    """Raised when the provided phone number does not match the appointment phone."""
    pass

class AppointmentStatusError(ValueError):
    """Raised when the operation is invalid for the current appointment status."""
    pass


# ── Operations ────────────────────────────────────────────────────────────────

def book_appointment(
    db: Session,
    slot_id: uuid.UUID,
    patient_name: str,
    patient_phone: str,
    reason: str | None = None,
    call_id: str | None = None
) -> Appointment:
    """
    Transaction-safe booking of a time slot.
    Locks the slot row using SELECT FOR UPDATE NOWAIT.
    """
    try:
        # Acquire lock on the slot
        slot = (
            db.query(Slot)
            .filter(Slot.id == slot_id)
            .with_for_update(nowait=True)
            .first()
        )
    except OperationalError as e:
        # PostgreSQL NOWAIT throws OperationalError when row is locked
        raise SlotUnavailableError("The requested slot is currently locked by another process.") from e

    if not slot:
        raise SlotNotFoundError(f"Slot {slot_id} does not exist.")

    if not slot.is_available:
        raise SlotUnavailableError("The requested slot is already booked.")

    # Mark slot as unavailable
    slot.is_available = False

    # Create the appointment record
    appointment = Appointment(
        slot_id=slot.id,
        doctor_id=slot.doctor_id,
        clinic_id=slot.doctor.clinic_id,
        patient_name=patient_name,
        patient_phone=patient_phone,
        reason=reason,
        call_id=call_id,
        status="confirmed"
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def reschedule_appointment(
    db: Session,
    appointment_id: uuid.UUID,
    new_slot_id: uuid.UUID,
    patient_phone: str
) -> Appointment:
    """
    Transaction-safe rescheduling.
    Frees the old slot, flags the old appointment as rescheduled,
    locks/books the new slot, and creates a new appointment record.
    """
    # 1. Fetch and lock original appointment
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .with_for_update(nowait=True)
        .first()
    )

    if not appointment:
        raise AppointmentNotFoundError(f"Appointment {appointment_id} not found.")

    if appointment.patient_phone != patient_phone:
        raise PatientPhoneMismatchError("Patient phone number verification failed.")

    if appointment.status != "confirmed":
        raise AppointmentStatusError(
            f"Cannot reschedule appointment with status '{appointment.status}'."
        )

    # 2. Fetch and lock the new slot
    try:
        new_slot = (
            db.query(Slot)
            .filter(Slot.id == new_slot_id)
            .with_for_update(nowait=True)
            .first()
        )
    except OperationalError as e:
        raise SlotUnavailableError("The requested new slot is locked by another process.") from e

    if not new_slot:
        raise SlotNotFoundError(f"New slot {new_slot_id} does not exist.")

    if not new_slot.is_available:
        raise SlotUnavailableError("The requested new slot is already booked.")

    # 3. Free old slot
    old_slot = db.query(Slot).filter(Slot.id == appointment.slot_id).first()
    if old_slot:
        old_slot.is_available = True

    # 4. Mark old appointment as rescheduled
    appointment.status = "rescheduled"
    appointment.rescheduled_at = datetime.now(timezone.utc)

    # 5. Lock new slot and create new appointment
    new_slot.is_available = False

    new_appointment = Appointment(
        slot_id=new_slot.id,
        doctor_id=new_slot.doctor_id,
        clinic_id=new_slot.doctor.clinic_id,
        patient_name=appointment.patient_name,
        patient_phone=patient_phone,
        reason=appointment.reason,
        call_id=appointment.call_id,
        original_slot_id=appointment.slot_id,
        status="confirmed"
    )
    db.add(new_appointment)
    db.commit()
    db.refresh(new_appointment)
    return new_appointment


def cancel_appointment(
    db: Session,
    appointment_id: uuid.UUID,
    patient_phone: str,
    cancellation_reason: str | None = None
) -> Appointment:
    """
    Transaction-safe cancellation.
    Frees the booked slot and marks the appointment as cancelled.
    """
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .with_for_update(nowait=True)
        .first()
    )

    if not appointment:
        raise AppointmentNotFoundError(f"Appointment {appointment_id} not found.")

    if appointment.patient_phone != patient_phone:
        raise PatientPhoneMismatchError("Patient phone number verification failed.")

    if appointment.status != "confirmed":
        raise AppointmentStatusError(
            f"Cannot cancel appointment with status '{appointment.status}'."
        )

    # Free the slot
    slot = db.query(Slot).filter(Slot.id == appointment.slot_id).first()
    if slot:
        slot.is_available = True

    # Cancel the appointment
    appointment.status = "cancelled"
    appointment.cancellation_reason = cancellation_reason
    appointment.cancelled_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(appointment)
    return appointment
