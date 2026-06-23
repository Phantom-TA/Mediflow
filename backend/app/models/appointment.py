"""
Appointment model.

The core booking record. Created when a patient successfully books a slot.

Status lifecycle:
  confirmed → cancelled        (patient cancels)
  confirmed → rescheduled      (patient reschedules; a NEW appointment row is created)
  confirmed → completed        (post-appointment, set by admin/system)
  confirmed → no_show          (patient did not attend)

On reschedule:
  - Old appointment: status='rescheduled', rescheduled_at=now()
  - Old slot: is_available=true (freed)
  - New appointment: status='confirmed', original_slot_id=old_slot_id
  - New slot: is_available=false

CRITICAL:
  - UNIQUE(slot_id) — one appointment per slot, DB-level guard
  - patient_phone verification required for reschedule/cancel
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.slot import Slot
    from app.models.doctor import Doctor
    from app.models.clinic import Clinic
    from app.models.conversation import ConversationSession

VALID_STATUSES = ("confirmed", "cancelled", "rescheduled", "completed", "no_show")


class Appointment(Base):
    __tablename__ = "appointments"

    __table_args__ = (
        # One appointment per slot — secondary double-booking guard
        UniqueConstraint("slot_id", name="uq_slot_appointment"),
        CheckConstraint(
            f"status IN {VALID_STATUSES}",
            name="ck_appointment_valid_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("slots.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="RESTRICT"),
        nullable=False,
    )
    patient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    patient_phone: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="confirmed", index=True
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set on reschedule — points to the slot that was freed
    original_slot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("slots.id"),
        nullable=True,
    )
    # Vapi call ID for full traceability
    call_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    booked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rescheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────────────────
    slot: Mapped["Slot"] = relationship(  # noqa: F821
        "Slot",
        foreign_keys=[slot_id],
        back_populates="appointment",
    )
    doctor: Mapped["Doctor"] = relationship(  # noqa: F821
        "Doctor", back_populates="appointments"
    )
    clinic: Mapped["Clinic"] = relationship(  # noqa: F821
        "Clinic", back_populates="appointments"
    )
    conversation_session: Mapped["ConversationSession | None"] = relationship(  # noqa: F821
        "ConversationSession",
        foreign_keys="[ConversationSession.appointment_id]",
        back_populates="appointment",
        uselist=False,
    )

    @property
    def is_confirmed(self) -> bool:
        return self.status == "confirmed"

    @property
    def is_active(self) -> bool:
        return self.status in ("confirmed",)

    def __repr__(self) -> str:
        return (
            f"<Appointment id={self.id} patient={self.patient_name!r} "
            f"status={self.status!r}>"
        )
