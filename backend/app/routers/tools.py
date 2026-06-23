from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings, Settings
from app.models.doctor import Doctor
from app.models.slot import Slot
from app.models.appointment import Appointment
from app.services.appointment_engine import (
    book_appointment,
    reschedule_appointment,
    cancel_appointment,
    SlotNotFoundError,
    SlotUnavailableError,
    AppointmentNotFoundError,
    PatientPhoneMismatchError,
    AppointmentStatusError,
)
from app.schemas.tools import (
    APIResponse,
    FindDoctorsRequest,
    FindDoctorsResponseData,
    DoctorListItem,
    CheckAvailabilityRequest,
    CheckAvailabilityResponseData,
    DoctorMini,
    SlotListItem,
    RecommendAlternativesRequest,
    RecommendAlternativesResponseData,
    AlternativeItem,
    BookAppointmentRequest,
    AppointmentBookingData,
    RescheduleAppointmentRequest,
    RescheduleAppointmentData,
    CancelAppointmentRequest,
    CancelAppointmentData,
    FindPatientAppointmentsRequest,
    FindPatientAppointmentsData,
    PatientAppointmentItem,
    get_ordinal_suffix,
)

router = APIRouter()

# ── Authentication Dependency ──────────────────────────────────────────────────

def verify_vapi_secret(
    x_vapi_secret: str | None = Header(None, alias="X-Vapi-Secret"),
    settings: Settings = Depends(get_settings)
):
    if settings.vapi_secret and x_vapi_secret != settings.vapi_secret:
        raise HTTPException(
            status_code=401,
            detail={
                "success": False,
                "error_code": "UNAUTHORIZED",
                "error_message": "Invalid X-Vapi-Secret header value.",
                "data": None
            }
        )


# ── Time Formatting Helpers ───────────────────────────────────────────────────

def to_ist_iso(dt_utc: datetime) -> str:
    ist_tz = ZoneInfo("Asia/Kolkata")
    return dt_utc.astimezone(ist_tz).isoformat()


def format_confirmation_datetime(dt_utc: datetime) -> str:
    ist_tz = ZoneInfo("Asia/Kolkata")
    dt_ist = dt_utc.astimezone(ist_tz)
    day_name = dt_ist.strftime("%A")
    day_num = dt_ist.day
    suffix = get_ordinal_suffix(day_num)
    month_name = dt_ist.strftime("%B")
    time_str = dt_ist.strftime("%I:%M %p").lstrip("0")
    return f"{day_name} {suffix} {month_name} at {time_str}"


def format_cancellation_datetime(dt_utc: datetime) -> str:
    ist_tz = ZoneInfo("Asia/Kolkata")
    dt_ist = dt_utc.astimezone(ist_tz)
    month_name = dt_ist.strftime("%B")
    day_num = dt_ist.day
    suffix = get_ordinal_suffix(day_num)
    time_str = dt_ist.strftime("%I:%M %p").lstrip("0")
    return f"{month_name} {suffix} at {time_str}"


# ── API Endpoints ─────────────────────────────────────────────────────────────

@router.post("/find_doctors", response_model=APIResponse, dependencies=[Depends(verify_vapi_secret)])
def find_doctors(req: FindDoctorsRequest, db: Session = Depends(get_db)):
    """Find active doctors by specialty or name."""
    query = db.query(Doctor).filter(Doctor.is_active.is_(True))

    if req.clinic_id:
        query = query.filter(Doctor.clinic_id == req.clinic_id)

    if req.specialty and req.name_query:
        query = query.filter(
            Doctor.specialty.ilike(f"%{req.specialty}%") | Doctor.name.ilike(f"%{req.name_query}%")
        )
    elif req.specialty:
        query = query.filter(Doctor.specialty.ilike(f"%{req.specialty}%"))
    elif req.name_query:
        query = query.filter(Doctor.name.ilike(f"%{req.name_query}%"))

    # Sort results
    doctors = query.order_by(Doctor.experience_years.desc(), Doctor.name.asc()).all()

    now_utc = datetime.now(timezone.utc)
    doctors_list = []

    for doc in doctors:
        # Find earliest available slot
        earliest_slot = (
            db.query(Slot)
            .filter(Slot.doctor_id == doc.id, Slot.is_available.is_(True), Slot.slot_start >= now_utc)
            .order_by(Slot.slot_start.asc())
            .first()
        )
        next_available = to_ist_iso(earliest_slot.slot_start) if earliest_slot else None

        doctors_list.append(
            DoctorListItem(
                id=doc.id,
                name=doc.full_name,
                specialty=doc.specialty,
                department=doc.department,
                qualifications=doc.qualifications,
                experience_years=doc.experience_years,
                designation=doc.designation,
                next_available=next_available,
            )
        )

    return APIResponse(
        success=True,
        data=FindDoctorsResponseData(doctors=doctors_list, total=len(doctors_list)),
    )


@router.post("/check_availability", response_model=APIResponse, dependencies=[Depends(verify_vapi_secret)])
def check_availability(req: CheckAvailabilityRequest, db: Session = Depends(get_db)):
    """Get active slots for a doctor on a given date or range."""
    doctor = db.query(Doctor).filter(Doctor.id == req.doctor_id, Doctor.is_active.is_(True)).first()
    if not doctor:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error_code": "DOCTOR_NOT_FOUND",
                "error_message": "Doctor not found or inactive.",
                "data": None
            }
        )

    ist_tz = ZoneInfo("Asia/Kolkata")
    today_ist = datetime.now(ist_tz).date()

    # Validate 14 day window bounds
    if req.date < today_ist or req.date > today_ist + timedelta(days=14):
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error_code": "INVALID_DATE_RANGE",
                "error_message": "Date is in the past or beyond the 14-day window.",
                "data": None
            }
        )

    # Construct UTC datetime boundaries for the requested date(s)
    start_dt_ist = datetime.combine(req.date, time.min).replace(tzinfo=ist_tz)
    start_dt_utc = start_dt_ist.astimezone(timezone.utc)

    end_date = req.date_end if req.date_end else req.date
    end_dt_ist = datetime.combine(end_date, time.max).replace(tzinfo=ist_tz)
    end_dt_utc = end_dt_ist.astimezone(timezone.utc)

    # If query includes today, only allow future slots
    now_utc = datetime.now(timezone.utc)
    query_start = max(start_dt_utc, now_utc)

    slots = (
        db.query(Slot)
        .filter(
            Slot.doctor_id == req.doctor_id,
            Slot.is_available.is_(True),
            Slot.slot_start >= query_start,
            Slot.slot_start <= end_dt_utc,
        )
        .order_by(Slot.slot_start.asc())
        .all()
    )

    slots_list = [
        SlotListItem(
            id=s.id,
            slot_start=to_ist_iso(s.slot_start),
            slot_end=to_ist_iso(s.slot_end),
            is_available=s.is_available,
        )
        for s in slots
    ]

    return APIResponse(
        success=True,
        data=CheckAvailabilityResponseData(
            doctor=DoctorMini(id=doctor.id, name=doctor.full_name, specialty=doctor.specialty),
            date=req.date.isoformat(),
            slots=slots_list,
            total_available=len(slots_list),
        ),
    )


@router.post("/recommend_alternatives", response_model=APIResponse, dependencies=[Depends(verify_vapi_secret)])
def recommend_alternatives(req: RecommendAlternativesRequest, db: Session = Depends(get_db)):
    """Heuristic slot ranking for alternative recommendations."""
    ist_tz = ZoneInfo("Asia/Kolkata")
    now_utc = datetime.now(timezone.utc)

    # Query all active doctors in this specialty
    doctors = db.query(Doctor).filter(Doctor.specialty.ilike(f"%{req.specialty}%"), Doctor.is_active.is_(True)).all()
    if not doctors:
        return APIResponse(success=True, data=RecommendAlternativesResponseData(alternatives=[]))

    doctor_ids = [doc.id for doc in doctors]
    doctor_map = {doc.id: doc for doc in doctors}

    # Query all available slots in next 14 days
    slots = (
        db.query(Slot)
        .filter(
            Slot.doctor_id.in_(doctor_ids),
            Slot.is_available.is_(True),
            Slot.slot_start >= now_utc,
            Slot.slot_start <= now_utc + timedelta(days=14),
        )
        .all()
    )

    # Compute score for each slot
    scored_slots = []
    preferred_min = None
    if req.preferred_time:
        try:
            h, m = map(int, req.preferred_time.split(":"))
            preferred_min = h * 60 + m
        except Exception:
            pass

    for s in slots:
        score = 0.0
        # 1. Same doctor bonus (40%)
        if req.preferred_doctor_id and s.doctor_id == req.preferred_doctor_id:
            score += 0.40

        # 2. Same specialty bonus (20%) - all queried slots have this
        score += 0.20

        s_ist = s.slot_start.astimezone(ist_tz)

        # 3. Date proximity (20%)
        days_diff = abs((s_ist.date() - req.preferred_date).days)
        score += 0.20 * max(0.0, 1.0 - (days_diff / 14.0))

        # 4. Time proximity (20%)
        if preferred_min is not None:
            slot_min = s_ist.hour * 60 + s_ist.minute
            min_diff = abs(slot_min - preferred_min)
            score += 0.20 * max(0.0, 1.0 - (min_diff / 720.0))  # within 12h range
        else:
            score += 0.20

        scored_slots.append((score, s))

    # Sort by score DESC, then slot start ASC
    scored_slots.sort(key=lambda x: (-x[0], x[1].slot_start))

    alternatives = []
    for i, (score, s) in enumerate(scored_slots[:req.max_results]):
        doc = doctor_map[s.doctor_id]
        reason = "Same doctor, closest available slot" if req.preferred_doctor_id and s.doctor_id == req.preferred_doctor_id else "Same specialty, closest available slot"
        alternatives.append(
            AlternativeItem(
                rank=i + 1,
                doctor=DoctorMini(id=doc.id, name=doc.full_name, specialty=doc.specialty),
                slot=SlotListItem(
                    id=s.id,
                    slot_start=to_ist_iso(s.slot_start),
                    slot_end=to_ist_iso(s.slot_end),
                    is_available=s.is_available,
                ),
                reason=reason,
                score=round(score, 2),
            )
        )

    return APIResponse(
        success=True,
        data=RecommendAlternativesResponseData(alternatives=alternatives),
    )


@router.post("/book_appointment", response_model=APIResponse, dependencies=[Depends(verify_vapi_secret)])
def book_appointment_endpoint(req: BookAppointmentRequest, db: Session = Depends(get_db)):
    """Book a time slot."""
    try:
        app = book_appointment(
            db=db,
            slot_id=req.slot_id,
            patient_name=req.patient_name,
            patient_phone=req.patient_phone,
            reason=req.reason,
            call_id=req.call_id,
        )
    except SlotNotFoundError:
        raise HTTPException(
            status_code=409,
            detail={
                "success": False,
                "error_code": "SLOT_UNAVAILABLE",
                "error_message": "The requested slot no longer exists.",
                "data": None
            }
        )
    except SlotUnavailableError:
        raise HTTPException(
            status_code=409,
            detail={
                "success": False,
                "error_code": "SLOT_UNAVAILABLE",
                "error_message": f"The slot with Dr. {db.query(Doctor).filter(Doctor.id == req.doctor_id).first().name} is no longer available.",
                "data": None
            }
        )

    formatted_time = format_confirmation_datetime(app.slot.slot_start)
    conf_msg = f"Appointment confirmed with {app.doctor.full_name} on {formatted_time}."

    return APIResponse(
        success=True,
        data=AppointmentBookingData(
            appointment_id=app.id,
            doctor_name=app.doctor.full_name,
            specialty=app.doctor.specialty,
            slot_start=to_ist_iso(app.slot.slot_start),
            slot_end=to_ist_iso(app.slot.slot_end),
            patient_name=app.patient_name,
            patient_phone=app.patient_phone,
            status=app.status,
            confirmation_message=conf_msg,
        ),
    )


@router.post("/reschedule_appointment", response_model=APIResponse, dependencies=[Depends(verify_vapi_secret)])
def reschedule_appointment_endpoint(req: RescheduleAppointmentRequest, db: Session = Depends(get_db)):
    """Reschedule a confirmed appointment."""
    try:
        new_app = reschedule_appointment(
            db=db,
            appointment_id=req.appointment_id,
            new_slot_id=req.new_slot_id,
            patient_phone=req.patient_phone,
        )
    except AppointmentNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error_code": "APPOINTMENT_NOT_FOUND",
                "error_message": "Appointment not found.",
                "data": None
            }
        )
    except PatientPhoneMismatchError:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error_code": "VALIDATION_ERROR",
                "error_message": "Patient phone number verification failed.",
                "data": None
            }
        )
    except AppointmentStatusError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error_code": "VALIDATION_ERROR",
                "error_message": str(e),
                "data": None
            }
        )
    except SlotNotFoundError:
        raise HTTPException(
            status_code=409,
            detail={
                "success": False,
                "error_code": "SLOT_UNAVAILABLE",
                "error_message": "The requested new slot does not exist.",
                "data": None
            }
        )
    except SlotUnavailableError:
        raise HTTPException(
            status_code=409,
            detail={
                "success": False,
                "error_code": "SLOT_UNAVAILABLE",
                "error_message": "The requested new slot is already booked.",
                "data": None
            }
        )

    formatted_time = format_confirmation_datetime(new_app.slot.slot_start)
    conf_msg = f"Rescheduled to {formatted_time} with {new_app.doctor.full_name}."

    # Look up old slot start time
    old_slot_start = ""
    if new_app.original_slot_id:
        old_slot = db.query(Slot).filter(Slot.id == new_app.original_slot_id).first()
        if old_slot:
            old_slot_start = to_ist_iso(old_slot.slot_start)

    return APIResponse(
        success=True,
        data=RescheduleAppointmentData(
            old_appointment_id=req.appointment_id,
            new_appointment_id=new_app.id,
            doctor_name=new_app.doctor.full_name,
            old_slot_start=old_slot_start,
            new_slot_start=to_ist_iso(new_app.slot.slot_start),
            status=new_app.status,
            confirmation_message=conf_msg,
        ),
    )


@router.post("/cancel_appointment", response_model=APIResponse, dependencies=[Depends(verify_vapi_secret)])
def cancel_appointment_endpoint(req: CancelAppointmentRequest, db: Session = Depends(get_db)):
    """Cancel a confirmed appointment."""
    try:
        app = cancel_appointment(
            db=db,
            appointment_id=req.appointment_id,
            patient_phone=req.patient_phone,
            cancellation_reason=req.reason,
        )
    except AppointmentNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error_code": "APPOINTMENT_NOT_FOUND",
                "error_message": "Appointment not found.",
                "data": None
            }
        )
    except PatientPhoneMismatchError:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error_code": "VALIDATION_ERROR",
                "error_message": "Patient phone number verification failed.",
                "data": None
            }
        )
    except AppointmentStatusError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error_code": "VALIDATION_ERROR",
                "error_message": str(e),
                "data": None
            }
        )

    formatted_time = format_cancellation_datetime(app.slot.slot_start)
    conf_msg = f"Your appointment with {app.doctor.full_name} on {formatted_time} has been cancelled."

    return APIResponse(
        success=True,
        data=CancelAppointmentData(
            appointment_id=app.id,
            doctor_name=app.doctor.full_name,
            slot_start=to_ist_iso(app.slot.slot_start),
            status=app.status,
            confirmation_message=conf_msg,
        ),
    )


@router.post("/find_patient_appointments", response_model=APIResponse, dependencies=[Depends(verify_vapi_secret)])
def find_patient_appointments(req: FindPatientAppointmentsRequest, db: Session = Depends(get_db)):
    """Find appointments associated with a patient's phone number."""
    query = db.query(Appointment).join(Slot, Appointment.slot_id == Slot.id)
    query = query.filter(Appointment.patient_phone == req.patient_phone)

    now_utc = datetime.now(timezone.utc)

    if req.status_filter == "confirmed":
        query = query.filter(Appointment.status == "confirmed", Slot.slot_start >= now_utc)
    elif req.status_filter in ("cancelled", "rescheduled"):
        query = query.filter(Appointment.status == req.status_filter)
    elif req.status_filter != "all":
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid status_filter '{req.status_filter}'. Allowed: confirmed, cancelled, rescheduled, all.",
                "data": None
            }
        )

    appointments = query.order_by(Slot.slot_start.asc()).all()

    if not appointments:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error_code": "PATIENT_NOT_FOUND",
                "error_message": "No appointments found for this phone number.",
                "data": None
            }
        )

    app_list = [
        PatientAppointmentItem(
            id=a.id,
            doctor_name=a.doctor.full_name,
            specialty=a.doctor.specialty,
            slot_start=to_ist_iso(a.slot.slot_start),
            slot_end=to_ist_iso(a.slot.slot_end),
            status=a.status,
            booked_at=to_ist_iso(a.booked_at),
        )
        for a in appointments
    ]

    return APIResponse(
        success=True,
        data=FindPatientAppointmentsData(appointments=app_list, total=len(app_list)),
    )
