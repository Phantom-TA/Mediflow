"""
Initial schema — create all MediFlow tables.

Revision ID: 001
Revises: —
Create Date: 2026-06-22 06:00:00 UTC
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── clinics ───────────────────────────────────────────────────────────
    op.create_table(
        "clinics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.Text, nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("website_url", sa.Text, nullable=True),
        sa.Column("source_url", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    # ── doctors ───────────────────────────────────────────────────────────
    op.create_table(
        "doctors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("salutation", sa.String(20), nullable=False, server_default="'Dr.'"),
        sa.Column("specialty", sa.String(100), nullable=False),
        sa.Column("department", sa.String(200), nullable=False),
        sa.Column("qualifications", sa.Text, nullable=False),
        sa.Column("experience_years", sa.Integer, nullable=True),
        sa.Column("designation", sa.String(200), nullable=True),
        sa.Column("languages", postgresql.ARRAY(sa.String), nullable=True),
        sa.Column("source_url", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_doctors_clinic_id", "doctors", ["clinic_id"])
    op.create_index("idx_doctors_specialty", "doctors", ["specialty"])
    op.create_index("idx_doctors_is_active", "doctors", ["is_active"])

    # ── availability ──────────────────────────────────────────────────────
    op.create_table(
        "availability",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger, nullable=False),
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        sa.Column("slot_duration", sa.SmallInteger, nullable=False, server_default="15"),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="'Asia/Kolkata'"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("source_url", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="CASCADE"),
        sa.CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_availability_day_of_week"),
        sa.CheckConstraint("end_time > start_time", name="ck_availability_valid_times"),
        sa.CheckConstraint("slot_duration IN (10, 15, 20, 30)", name="ck_availability_slot_duration"),
    )
    op.create_index("idx_availability_doctor_id", "availability", ["doctor_id"])
    op.create_index("idx_availability_day", "availability", ["day_of_week"])

    # ── slots ─────────────────────────────────────────────────────────────
    op.create_table(
        "slots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("availability_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slot_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("slot_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_available", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["availability_id"], ["availability.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("doctor_id", "slot_start", name="uq_doctor_slot"),
        sa.CheckConstraint("slot_end > slot_start", name="ck_slot_valid_window"),
    )
    op.create_index("idx_slots_doctor_id", "slots", ["doctor_id"])
    op.create_index("idx_slots_slot_start", "slots", ["slot_start"])
    op.create_index("idx_slots_is_available", "slots", ["is_available"])
    # Partial index: fast lookup of available slots per doctor
    op.execute(
        """
        CREATE INDEX ix_slots_doctor_available
        ON slots (doctor_id, slot_start)
        WHERE is_available = true
        """
    )

    # ── appointments ──────────────────────────────────────────────────────
    op.create_table(
        "appointments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("slot_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_name", sa.String(255), nullable=False),
        sa.Column("patient_phone", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="'confirmed'"),
        sa.Column("cancellation_reason", sa.Text, nullable=True),
        sa.Column("original_slot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("call_id", sa.String(100), nullable=True),
        sa.Column("booked_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rescheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["slot_id"], ["slots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["original_slot_id"], ["slots.id"]),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("slot_id", name="uq_slot_appointment"),
        sa.CheckConstraint(
            "status IN ('confirmed', 'cancelled', 'rescheduled', 'completed', 'no_show')",
            name="ck_appointment_valid_status",
        ),
    )
    op.create_index("idx_appointments_patient_phone", "appointments", ["patient_phone"])
    op.create_index("idx_appointments_doctor_id", "appointments", ["doctor_id"])
    op.create_index("idx_appointments_status", "appointments", ["status"])
    op.create_index("idx_appointments_call_id", "appointments", ["call_id"])

    # ── conversation_sessions ─────────────────────────────────────────────
    op.create_table(
        "conversation_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("call_id", sa.String(100), nullable=False, unique=True),
        sa.Column("patient_phone", sa.String(30), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(30), nullable=True),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"]),
    )
    op.create_index("idx_sessions_call_id", "conversation_sessions", ["call_id"])
    op.create_index("idx_sessions_patient_phone", "conversation_sessions", ["patient_phone"])

    # ── conversation_state ────────────────────────────────────────────────
    op.create_table(
        "conversation_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("call_id", sa.String(100), nullable=False, unique=True),
        sa.Column("intent", sa.String(20), nullable=True),
        sa.Column("patient_name", sa.String(255), nullable=True),
        sa.Column("patient_phone", sa.String(30), nullable=True),
        sa.Column("selected_department", sa.String(100), nullable=True),
        sa.Column("selected_doctor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("selected_slot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("current_appointment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("confirmation_pending", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["call_id"], ["conversation_sessions.call_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["selected_doctor_id"], ["doctors.id"]),
        sa.ForeignKeyConstraint(["selected_slot_id"], ["slots.id"]),
        sa.ForeignKeyConstraint(["current_appointment_id"], ["appointments.id"]),
    )
    op.create_index("idx_conv_state_call_id", "conversation_state", ["call_id"])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("conversation_state")
    op.drop_table("conversation_sessions")
    op.drop_table("appointments")
    op.execute("DROP INDEX IF EXISTS ix_slots_doctor_available")
    op.drop_table("slots")
    op.drop_table("availability")
    op.drop_table("doctors")
    op.drop_table("clinics")
