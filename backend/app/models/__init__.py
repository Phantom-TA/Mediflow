"""
Models package — exports all ORM models so Alembic can discover them.
Import order matters: Base must be imported before models that reference it.
"""

from app.database import Base  # noqa: F401

from app.models.clinic import Clinic  # noqa: F401
from app.models.doctor import Doctor  # noqa: F401
from app.models.availability import Availability  # noqa: F401
from app.models.slot import Slot  # noqa: F401
from app.models.appointment import Appointment  # noqa: F401
from app.models.conversation import ConversationSession, ConversationState  # noqa: F401

__all__ = [
    "Base",
    "Clinic",
    "Doctor",
    "Availability",
    "Slot",
    "Appointment",
    "ConversationSession",
    "ConversationState",
]
