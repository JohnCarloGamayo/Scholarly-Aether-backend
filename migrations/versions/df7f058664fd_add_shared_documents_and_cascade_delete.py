"""add_shared_documents_and_cascade_delete

Revision ID: df7f058664fd
Revises: f1ac8f31f761
Create Date: 2026-04-01 13:06:48.599941

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df7f058664fd'
down_revision: Union[str, None] = 'f1ac8f31f761'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create shared_documents table if it doesn't exist
    from sqlalchemy import inspect
    from alembic import context
    
    conn = context.get_bind()
    inspector = inspect(conn)
    
    if 'shared_documents' not in inspector.get_table_names():
        op.create_table(
            'shared_documents',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('document_id', sa.UUID(), nullable=False),
            sa.Column('group_id', sa.UUID(), nullable=False),
            sa.Column('shared_by_id', sa.UUID(), nullable=False),
            sa.Column('shared_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['shared_by_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id')
        )
    
    # Update foreign key constraints to add CASCADE delete
    # Drop existing foreign key
    op.drop_constraint('documents_crawl_job_id_fkey', 'documents', type_='foreignkey')
    # Recreate with CASCADE
    op.create_foreign_key(
        'documents_crawl_job_id_fkey',
        'documents', 'crawl_jobs',
        ['crawl_job_id'], ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    # Drop shared_documents table
    op.drop_table('shared_documents')
    
    # Revert foreign key constraint
    op.drop_constraint('documents_crawl_job_id_fkey', 'documents', type_='foreignkey')
    op.create_foreign_key(
        'documents_crawl_job_id_fkey',
        'documents', 'crawl_jobs',
        ['crawl_job_id'], ['id']
    )
