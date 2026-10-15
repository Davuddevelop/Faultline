"""The v0 schema: workspaces, people, tokens, runners, programs, checkpoints,
campaigns and their jobs, evaluations, failure modes, artifacts, gates, and the
audit log.

Revision ID: 0001
Revises: 
Created: 2026-10-09 18:24:33.684935
"""
from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('workos_id', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('workos_id')
    )
    op.create_table('workspaces',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('slug', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_table('audit_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('workspace_id', sa.String(length=32), nullable=False),
    sa.Column('actor', sa.String(length=200), nullable=False),
    sa.Column('action', sa.String(length=100), nullable=False),
    sa.Column('target', sa.String(length=200), nullable=False),
    sa.Column('detail', sa.JSON(), nullable=False),
    sa.Column('ip', sa.String(length=64), nullable=False),
    sa.Column('at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.create_index('ix_audit_ws_at', ['workspace_id', 'at'], unique=False)

    op.create_table('memberships',
    sa.Column('workspace_id', sa.String(length=32), nullable=False),
    sa.Column('user_id', sa.String(length=32), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('workspace_id', 'user_id')
    )
    op.create_table('programs',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('workspace_id', sa.String(length=32), nullable=False),
    sa.Column('slug', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('standard_spec', sa.JSON(), nullable=False),
    sa.Column('baseline_checkpoint_id', sa.String(length=32), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('workspace_id', 'slug')
    )
    with op.batch_alter_table('programs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_programs_workspace_id'), ['workspace_id'], unique=False)

    op.create_table('sign_in_links',
    sa.Column('code_sha256', sa.String(length=64), nullable=False),
    sa.Column('workspace_id', sa.String(length=32), nullable=False),
    sa.Column('user_id', sa.String(length=32), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('used_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('code_sha256')
    )
    op.create_table('tokens',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('workspace_id', sa.String(length=32), nullable=False),
    sa.Column('kind', sa.String(length=8), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('prefix', sa.String(length=24), nullable=False),
    sa.Column('secret_sha256', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.String(length=32), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('last_used_at', sa.DateTime(), nullable=True),
    sa.Column('revoked_at', sa.DateTime(), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('secret_sha256')
    )
    with op.batch_alter_table('tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tokens_workspace_id'), ['workspace_id'], unique=False)

    op.create_table('checkpoints',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('workspace_id', sa.String(length=32), nullable=False),
    sa.Column('program_id', sa.String(length=32), nullable=False),
    sa.Column('label', sa.String(length=64), nullable=False),
    sa.Column('policy', sa.String(length=100), nullable=False),
    sa.Column('policy_id', sa.String(length=200), nullable=True),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('program_id', 'label')
    )
    with op.batch_alter_table('checkpoints', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_checkpoints_program_id'), ['program_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_checkpoints_workspace_id'), ['workspace_id'], unique=False)

    op.create_table('runners',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('workspace_id', sa.String(length=32), nullable=False),
    sa.Column('token_id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('host', sa.JSON(), nullable=False),
    sa.Column('versions', sa.JSON(), nullable=False),
    sa.Column('cores', sa.Integer(), nullable=False),
    sa.Column('robots', sa.JSON(), nullable=False),
    sa.Column('policies', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['token_id'], ['tokens.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('workspace_id', 'name')
    )
    with op.batch_alter_table('runners', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_runners_workspace_id'), ['workspace_id'], unique=False)

    op.create_table('campaigns',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('workspace_id', sa.String(length=32), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('program_id', sa.String(length=32), nullable=True),
    sa.Column('checkpoint_id', sa.String(length=32), nullable=True),
    sa.Column('spec', sa.JSON(), nullable=False),
    sa.Column('spec_sha256', sa.String(length=64), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('created_by', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('finished_at', sa.DateTime(), nullable=True),
    sa.Column('runner_id', sa.String(length=32), nullable=True),
    sa.Column('n_evaluations', sa.Integer(), nullable=False),
    sa.Column('n_failures', sa.Integer(), nullable=False),
    sa.Column('n_invalid', sa.Integer(), nullable=False),
    sa.Column('first_failure_index', sa.Integer(), nullable=True),
    sa.Column('progress', sa.JSON(), nullable=False),
    sa.Column('result', sa.JSON(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('cancel_requested', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['checkpoint_id'], ['checkpoints.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['runner_id'], ['runners.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('workspace_id', 'number')
    )
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_campaigns_spec_sha256'), ['spec_sha256'], unique=False)
        batch_op.create_index('ix_campaigns_ws_created', ['workspace_id', 'created_at'], unique=False)

    op.create_table('artifacts',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('workspace_id', sa.String(length=32), nullable=False),
    sa.Column('campaign_id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('storage_key', sa.String(length=400), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('campaign_id', 'name')
    )
    with op.batch_alter_table('artifacts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_artifacts_workspace_id'), ['workspace_id'], unique=False)

    op.create_table('evaluations',
    sa.Column('campaign_id', sa.String(length=32), nullable=False),
    sa.Column('index', sa.Integer(), nullable=False),
    sa.Column('iteration', sa.Integer(), nullable=False),
    sa.Column('perturbation', sa.JSON(), nullable=False),
    sa.Column('severity', sa.Float(), nullable=True),
    sa.Column('failed', sa.Boolean(), nullable=False),
    sa.Column('invalid', sa.Text(), nullable=True),
    sa.Column('violation', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('campaign_id', 'index')
    )
    op.create_table('failure_modes',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('campaign_id', sa.String(length=32), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('label', sa.String(length=300), nullable=False),
    sa.Column('predicate', sa.String(length=100), nullable=False),
    sa.Column('required', sa.JSON(), nullable=False),
    sa.Column('count', sa.Integer(), nullable=False),
    sa.Column('minimal', sa.JSON(), nullable=False),
    sa.Column('first_t', sa.Float(), nullable=False),
    sa.Column('locally_minimal', sa.Boolean(), nullable=False),
    sa.Column('evaluations', sa.Integer(), nullable=False),
    sa.Column('region', sa.JSON(), nullable=False),
    sa.Column('replay', sa.String(length=200), nullable=True),
    sa.Column('trace', sa.String(length=200), nullable=True),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('campaign_id', 'ordinal')
    )
    with op.batch_alter_table('failure_modes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_failure_modes_campaign_id'), ['campaign_id'], unique=False)

    op.create_table('gates',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('workspace_id', sa.String(length=32), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('program_id', sa.String(length=32), nullable=True),
    sa.Column('baseline_campaign_id', sa.String(length=32), nullable=False),
    sa.Column('candidate_campaign_id', sa.String(length=32), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('verdict', sa.String(length=16), nullable=True),
    sa.Column('comparison', sa.JSON(), nullable=True),
    sa.Column('created_by', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('decided_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['baseline_campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['candidate_campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('workspace_id', 'number')
    )
    with op.batch_alter_table('gates', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_gates_workspace_id'), ['workspace_id'], unique=False)

    op.create_table('jobs',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('workspace_id', sa.String(length=32), nullable=False),
    sa.Column('campaign_id', sa.String(length=32), nullable=False),
    sa.Column('robot', sa.String(length=100), nullable=False),
    sa.Column('policy', sa.String(length=100), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('max_attempts', sa.Integer(), nullable=False),
    sa.Column('lease_owner', sa.String(length=32), nullable=True),
    sa.Column('lease_expires_at', sa.DateTime(), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('campaign_id')
    )
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.create_index('ix_jobs_claim', ['workspace_id', 'state', 'created_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_index('ix_jobs_claim')

    op.drop_table('jobs')
    with op.batch_alter_table('gates', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_gates_workspace_id'))

    op.drop_table('gates')
    with op.batch_alter_table('failure_modes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_failure_modes_campaign_id'))

    op.drop_table('failure_modes')
    op.drop_table('evaluations')
    with op.batch_alter_table('artifacts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_artifacts_workspace_id'))

    op.drop_table('artifacts')
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.drop_index('ix_campaigns_ws_created')
        batch_op.drop_index(batch_op.f('ix_campaigns_spec_sha256'))

    op.drop_table('campaigns')
    with op.batch_alter_table('runners', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_runners_workspace_id'))

    op.drop_table('runners')
    with op.batch_alter_table('checkpoints', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_checkpoints_workspace_id'))
        batch_op.drop_index(batch_op.f('ix_checkpoints_program_id'))

    op.drop_table('checkpoints')
    with op.batch_alter_table('tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tokens_workspace_id'))

    op.drop_table('tokens')
    op.drop_table('sign_in_links')
    with op.batch_alter_table('programs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_programs_workspace_id'))

    op.drop_table('programs')
    op.drop_table('memberships')
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.drop_index('ix_audit_ws_at')

    op.drop_table('audit_events')
    op.drop_table('workspaces')
    op.drop_table('users')
