"""
Availability model.

Defines weekly recurring availability windows for each doctor.
The slot generation engine reads these records to materialise concrete
time slots 14 days into the future.

day_of_week convention: 0=Monday, 1=Tuesday, ..., 6=Sunday
(matches Python's datetime.weekday())
"""

import uuid
from datetime import datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class Availability(Base):
    __tablename__ = "availability"

    __table_args__ = (
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_availability_day_of_week"),
        CheckConstraint("end_time > start_time", name="ck_availability_valid_times"),
        CheckConstraint(
            "slot_duration IN (10, 15, 20, 30)", name="ck_availability_slot_duration"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 0=Monday, 6=Sunday — Python weekday() convention
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    # Slot duration in minutes — 10, 15, 20, or 30
    slot_duration: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=15)
    timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Asia/Kolkata"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # URL where this schedule was verified (doctor profile / appointment page)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # ── Relationships ─────────────────────────────────────────────────────
    doctor: Mapped["Doctor"] = relationship(  # noqa: F821
        "Doctor", back_populates="availabilities"
    )
    slots: Mapped[list["Slot"]] = relationship(  # noqa: F821
        "Slot", back_populates="availability"
    )

    @property
    def day_name(self) -> str:
        return DAY_NAMES[self.day_of_week]

    def __repr__(self) -> str:
        return (
            f"<Availability id={self.id} doctor_id={self.doctor_id} "
            f"day={self.day_name} {self.start_time}–{self.end_time}>"
        )
