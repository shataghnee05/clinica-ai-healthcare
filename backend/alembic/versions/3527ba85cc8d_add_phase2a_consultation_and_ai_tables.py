"""add_phase2a_consultation_and_ai_tables

Revision ID: 3527ba85cc8d
Revises: 26d626e45912
Create Date: 2026-08-23 12:15:18.881848

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '3527ba85cc8d'
down_revision: Union[str, Sequence[str], None] = '26d626e45912'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""

    op.create_table('background_jobs',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('job_type', sa.Enum('PRE_VISIT_SUMMARY', 'POST_VISIT_SUMMARY', name='jobtype'), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', name='jobstatus'), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('result', sa.JSON(), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('max_attempts', sa.Integer(), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('scheduled_at', sa.DateTime(), nullable=False),
    sa.Column('locked_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_background_jobs_job_type'), 'background_jobs', ['job_type'], unique=False)
    op.create_index(op.f('ix_background_jobs_scheduled_at'), 'background_jobs', ['scheduled_at'], unique=False)
    op.create_index(op.f('ix_background_jobs_status'), 'background_jobs', ['status'], unique=False)
    op.create_table('consultations',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('appointment_id', sa.String(length=36), nullable=False),
    sa.Column('doctor_id', sa.String(length=36), nullable=False),
    sa.Column('patient_id', sa.String(length=36), nullable=False),
    sa.Column('clinical_notes', sa.Text(), nullable=False),
    sa.Column('diagnosis', sa.Text(), nullable=False),
    sa.Column('follow_up_instructions', sa.Text(), nullable=False),
    sa.Column('status', sa.Enum('IN_PROGRESS', 'COMPLETED', name='consultationstatus'), nullable=False),
    sa.Column('started_at', sa.DateTime(), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['doctor_id'], ['doctor_profiles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_consultations_appointment_id'), 'consultations', ['appointment_id'], unique=True)
    op.create_index(op.f('ix_consultations_doctor_id'), 'consultations', ['doctor_id'], unique=False)
    op.create_index(op.f('ix_consultations_patient_id'), 'consultations', ['patient_id'], unique=False)
    op.create_table('pre_visit_summaries',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('appointment_id', sa.String(length=36), nullable=False),
    sa.Column('urgency', sa.Enum('LOW', 'MEDIUM', 'HIGH', name='urgencylevel'), nullable=False),
    sa.Column('chief_complaint', sa.Text(), nullable=False),
    sa.Column('suggested_questions', sa.JSON(), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'GENERATED', 'FAILED', name='aisummarystatus'), nullable=False),
    sa.Column('raw_response', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pre_visit_summaries_appointment_id'), 'pre_visit_summaries', ['appointment_id'], unique=True)
    op.create_table('post_visit_summaries',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('consultation_id', sa.String(length=36), nullable=False),
    sa.Column('visit_explanation', sa.Text(), nullable=False),
    sa.Column('medication_schedule', sa.JSON(), nullable=False),
    sa.Column('follow_up_steps', sa.Text(), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'GENERATED', 'FAILED', name='aisummarystatus'), nullable=False),
    sa.Column('raw_response', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['consultation_id'], ['consultations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_post_visit_summaries_consultation_id'), 'post_visit_summaries', ['consultation_id'], unique=True)
    op.create_table('prescriptions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('consultation_id', sa.String(length=36), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['consultation_id'], ['consultations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prescriptions_consultation_id'), 'prescriptions', ['consultation_id'], unique=True)
    op.create_table('medications',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('prescription_id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('dosage', sa.String(length=100), nullable=False),
    sa.Column('frequency', sa.String(length=100), nullable=False),
    sa.Column('duration', sa.String(length=100), nullable=False),
    sa.Column('instructions', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['prescription_id'], ['prescriptions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_medications_prescription_id'), 'medications', ['prescription_id'], unique=False)

def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(op.f('ix_medications_prescription_id'), table_name='medications')
    op.drop_table('medications')
    op.drop_index(op.f('ix_prescriptions_consultation_id'), table_name='prescriptions')
    op.drop_table('prescriptions')
    op.drop_index(op.f('ix_post_visit_summaries_consultation_id'), table_name='post_visit_summaries')
    op.drop_table('post_visit_summaries')
    op.drop_index(op.f('ix_pre_visit_summaries_appointment_id'), table_name='pre_visit_summaries')
    op.drop_table('pre_visit_summaries')
    op.drop_index(op.f('ix_consultations_patient_id'), table_name='consultations')
    op.drop_index(op.f('ix_consultations_doctor_id'), table_name='consultations')
    op.drop_index(op.f('ix_consultations_appointment_id'), table_name='consultations')
    op.drop_table('consultations')
    op.drop_index(op.f('ix_background_jobs_status'), table_name='background_jobs')
    op.drop_index(op.f('ix_background_jobs_scheduled_at'), table_name='background_jobs')
    op.drop_index(op.f('ix_background_jobs_job_type'), table_name='background_jobs')
    op.drop_table('background_jobs')

