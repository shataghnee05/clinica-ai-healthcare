from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '26d626e45912'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN CREATE TYPE userrole AS ENUM ('PATIENT', 'DOCTOR', 'ADMIN'); END IF; END $$;")
        op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'slotstatus') THEN CREATE TYPE slotstatus AS ENUM ('AVAILABLE', 'HELD', 'BOOKED', 'CANCELLED'); END IF; END $$;")
        op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'appointmentstatus') THEN CREATE TYPE appointmentstatus AS ENUM ('CONFIRMED', 'COMPLETED', 'CANCELLED'); END IF; END $$;")

        user_role_type = postgresql.ENUM('PATIENT', 'DOCTOR', 'ADMIN', name='userrole', create_type=False)
        slot_status_type = postgresql.ENUM('AVAILABLE', 'HELD', 'BOOKED', 'CANCELLED', name='slotstatus', create_type=False)
        appointment_status_type = postgresql.ENUM('CONFIRMED', 'COMPLETED', 'CANCELLED', name='appointmentstatus', create_type=False)
    else:
        user_role_type = sa.Enum('PATIENT', 'DOCTOR', 'ADMIN', name='userrole')
        slot_status_type = sa.Enum('AVAILABLE', 'HELD', 'BOOKED', 'CANCELLED', name='slotstatus')
        appointment_status_type = sa.Enum('CONFIRMED', 'COMPLETED', 'CANCELLED', name='appointmentstatus')

    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('role', user_role_type, nullable=False),
        sa.Column('accepted_insurance', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        if_not_exists=True
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True, if_not_exists=True)

    op.create_table(
        'doctor_profiles',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('specialization', sa.String(length=100), nullable=False),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('slot_duration_minutes', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        if_not_exists=True
    )
    op.create_index('ix_doctor_profiles_specialization', 'doctor_profiles', ['specialization'], if_not_exists=True)

    op.create_table(
        'doctor_working_hours',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('doctor_id', sa.String(length=36), sa.ForeignKey('doctor_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('is_day_off', sa.Boolean(), nullable=False, server_default='false'),
        sa.UniqueConstraint('doctor_id', 'day_of_week', name='uq_doctor_day'),
        if_not_exists=True
    )

    op.create_table(
        'slots',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('doctor_id', sa.String(length=36), sa.ForeignKey('doctor_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('status', slot_status_type, nullable=False),
        sa.Column('held_by_patient_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('hold_expires_at', sa.DateTime(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.UniqueConstraint('doctor_id', 'start_time', name='uq_doctor_slot_start'),
        if_not_exists=True
    )
    op.create_index('ix_slots_doctor_id', 'slots', ['doctor_id'], if_not_exists=True)
    op.create_index('ix_slots_start_time', 'slots', ['start_time'], if_not_exists=True)
    op.create_index('ix_slots_status', 'slots', ['status'], if_not_exists=True)
    op.create_index('ix_slots_hold_expires_at', 'slots', ['hold_expires_at'], if_not_exists=True)

    op.create_table(
        'appointments',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('slot_id', sa.String(length=36), sa.ForeignKey('slots.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('doctor_id', sa.String(length=36), sa.ForeignKey('doctor_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('patient_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('symptoms', sa.Text(), nullable=False),
        sa.Column('status', appointment_status_type, nullable=False),
        sa.Column('booked_at', sa.DateTime(), nullable=False),
        if_not_exists=True
    )
    op.create_index('ix_appointments_doctor_id', 'appointments', ['doctor_id'], if_not_exists=True)
    op.create_index('ix_appointments_patient_id', 'appointments', ['patient_id'], if_not_exists=True)

def downgrade() -> None:
    op.drop_table('appointments', if_exists=True)
    op.drop_table('slots', if_exists=True)
    op.drop_table('doctor_working_hours', if_exists=True)
    op.drop_table('doctor_profiles', if_exists=True)
    op.drop_table('users', if_exists=True)
