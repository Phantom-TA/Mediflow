"""
Doctor model.

Stores real doctors from Apollo Hospital Bannerghatta Road.
Every doctor record MUST have a source_url pointing to their Apollo profile.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    salutation: Mapped[str] = mapped_column(String(20), nullable=False, default="Dr.")
    specialty: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(200), nullable=False)
    qualifications: Mapped[str] = mapped_column(Text, nullable=False)
    experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    designation: Mapped[str | None] = mapped_column(String(200), nullable=True)
    languages: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
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
    clinic: Mapped["Clinic"] = relationship(  # noqa: F821
        "Clinic", back_populates="doctors"
    )
    availabilities: Mapped[list["Availability"]] = relationship(  # noqa: F821
        "Availability", back_populates="doctor", cascade="all, delete-orphan"
    )
    slots: Mapped[list["Slot"]] = relationship(  # noqa: F821
        "Slot", back_populates="doctor", cascade="all, delete-orphan"
    )
    appointments: Mapped[list["Appointment"]] = relationship(  # noqa: F821
        "Appointment", back_populates="doctor"
    )

    @property
    def full_name(self) -> str:
        return f"{self.salutation} {self.name}"

    def __repr__(self) -> str:
        return f"<Doctor id={self.id} name={self.full_name!r} specialty={self.specialty!r}>"
