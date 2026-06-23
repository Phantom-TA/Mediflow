"""
Conversation models.

ConversationSession: One record per Vapi phone call.
ConversationState:   Mid-conversation state snapshot, updated on every tool call.

The backend is the source of truth for all state.
The LLM reads state from tool responses — it never owns state.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.doctor import Doctor
    from app.models.slot import Slot

VALID_OUTCOMES = ("booked", "cancelled", "rescheduled", "abandoned", "out_of_scope")
VALID_INTENTS = ("book", "reschedule", "cancel", "unknown")


class ConversationSession(Base):
    """
    One record per Vapi call session.
    Created at call start (or on first tool call).
    """

    __tablename__ = "conversation_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # Vapi's unique call identifier
    call_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    patient_phone: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Final call outcome — set when session ends
    outcome: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # If a booking was completed, link to that appointment
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # ── Relationships ─────────────────────────────────────────────────────
    state: Mapped["ConversationState | None"] = relationship(
        "ConversationState",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )
    appointment: Mapped["Appointment | None"] = relationship(  # noqa: F821
        "Appointment",
        foreign_keys=[appointment_id],
        back_populates="conversation_session",
    )

    def __repr__(self) -> str:
        return f"<ConversationSession call_id={self.call_id!r} outcome={self.outcome!r}>"


class ConversationState(Base):
    """
    Persists mid-conversation state for a single call.
    Upserted on every tool invocation.
    """

    __tablename__ = "conversation_state"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # FK to conversation_sessions.call_id (string, not UUID)
    call_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("conversation_sessions.call_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    intent: Mapped[str | None] = mapped_column(String(20), nullable=True)
    patient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    patient_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    selected_department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    selected_doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id"),
        nullable=True,
    )
    selected_slot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("slots.id"),
        nullable=True,
    )
    current_appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id"),
        nullable=True,
    )
    confirmation_pending: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────────────────
    session: Mapped["ConversationSession"] = relationship(
        "ConversationSession", back_populates="state"
    )
    selected_doctor: Mapped["Doctor | None"] = relationship(  # noqa: F821
        "Doctor", foreign_keys=[selected_doctor_id]
    )
    selected_slot: Mapped["Slot | None"] = relationship(  # noqa: F821
        "Slot", foreign_keys=[selected_slot_id]
    )
    current_appointment: Mapped["Appointment | None"] = relationship(  # noqa: F821
        "Appointment", foreign_keys=[current_appointment_id]
    )

    def __repr__(self) -> str:
        return (
            f"<ConversationState call_id={self.call_id!r} "
            f"intent={self.intent!r} pending={self.confirmation_pending}>"
        )
