import uuid
from datetime import date
from pydantic import BaseModel, Field, model_validator
from typing import Any

# Helper to format numbers with ordinal suffixes
def get_ordinal_suffix(day: int) -> str:
    if 11 <= day <= 13:
        return f"{day}th"
    return {1: f"{day}st", 2: f"{day}nd", 3: f"{day}rd"}.get(day % 10, f"{day}th")


# ── Common Response Wrappers ──────────────────────────────────────────────────

class APIResponse(BaseModel):
    success: bool = True
    error_code: str | None = None
    error_message: str | None = None
    data: Any = None


# ── Find Doctors ──────────────────────────────────────────────────────────────

class FindDoctorsRequest(BaseModel):
    call_id: str
    specialty: str | None = None
    name_query: str | None = None
    clinic_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def verify_query_provided(self) -> "FindDoctorsRequest":
        if not self.specialty and not self.name_query:
            raise ValueError("At least one of 'specialty' or 'name_query' must be provided.")
        return self


class DoctorListItem(BaseModel):
    id: uuid.UUID
    name: str
    specialty: str
    department: str
    qualifications: str
    experience_years: int | None
    designation: str | None
    next_available: str | None = None


class FindDoctorsResponseData(BaseModel):
    doctors: list[DoctorListItem]
    total: int


# ── Check Availability ────────────────────────────────────────────────────────

class CheckAvailabilityRequest(BaseModel):
    call_id: str
    doctor_id: uuid.UUID
    date: date
    date_end: date | None = None


class SlotListItem(BaseModel):
    id: uuid.UUID
    slot_start: str
    slot_end: str
    is_available: bool


class DoctorMini(BaseModel):
    id: uuid.UUID
    name: str
    specialty: str


class CheckAvailabilityResponseData(BaseModel):
    doctor: DoctorMini
    date: str
    slots: list[SlotListItem]
    total_available: int


# ── Recommend Alternatives ────────────────────────────────────────────────────

class RecommendAlternativesRequest(BaseModel):
    call_id: str
    specialty: str
    preferred_doctor_id: uuid.UUID | None = None
    preferred_date: date
    preferred_time: str | None = None  # HH:MM format
    max_results: int = Field(default=5, ge=1)


class AlternativeItem(BaseModel):
    rank: int
    doctor: DoctorMini
    slot: SlotListItem
    reason: str
    score: float


class RecommendAlternativesResponseData(BaseModel):
    alternatives: list[AlternativeItem]


# ── Book Appointment ──────────────────────────────────────────────────────────

class BookAppointmentRequest(BaseModel):
    call_id: str
    slot_id: uuid.UUID
    doctor_id: uuid.UUID
    patient_name: str
    patient_phone: str
    reason: str | None = None


class AppointmentBookingData(BaseModel):
    appointment_id: uuid.UUID
    doctor_name: str
    specialty: str
    slot_start: str
    slot_end: str
    patient_name: str
    patient_phone: str
    status: str
    confirmation_message: str


# ── Reschedule Appointment ────────────────────────────────────────────────────

class RescheduleAppointmentRequest(BaseModel):
    call_id: str
    appointment_id: uuid.UUID
    new_slot_id: uuid.UUID
    patient_phone: str


class RescheduleAppointmentData(BaseModel):
    old_appointment_id: uuid.UUID
    new_appointment_id: uuid.UUID
    doctor_name: str
    old_slot_start: str
    new_slot_start: str
    status: str
    confirmation_message: str


# ── Cancel Appointment ────────────────────────────────────────────────────────

class CancelAppointmentRequest(BaseModel):
    call_id: str
    appointment_id: uuid.UUID
    patient_phone: str
    reason: str | None = None


class CancelAppointmentData(BaseModel):
    appointment_id: uuid.UUID
    doctor_name: str
    slot_start: str
    status: str
    confirmation_message: str


# ── Find Patient Appointments ──────────────────────────────────────────────────

class FindPatientAppointmentsRequest(BaseModel):
    call_id: str
    patient_phone: str
    status_filter: str = "confirmed"


class PatientAppointmentItem(BaseModel):
    id: uuid.UUID
    doctor_name: str
    specialty: str
    slot_start: str
    slot_end: str
    status: str
    booked_at: str


class FindPatientAppointmentsData(BaseModel):
    appointments: list[PatientAppointmentItem]
    total: int


# ── Vapi Webhook ──────────────────────────────────────────────────────────────

class VapiFunction(BaseModel):
    name: str
    arguments: str  # JSON String of arguments


class VapiToolCall(BaseModel):
    id: str
    type: str = "function"
    function: VapiFunction


class VapiCallMini(BaseModel):
    id: str
    phoneNumber: str | None = None


class VapiWebhookMessage(BaseModel):
    type: str = "tool-calls"
    toolCallList: list[VapiToolCall]
    call: VapiCallMini


class VapiWebhookRequest(BaseModel):
    message: VapiWebhookMessage


class VapiToolResult(BaseModel):
    toolCallId: str
    result: str  # JSON String response


class VapiWebhookResponse(BaseModel):
    results: list[VapiToolResult]
