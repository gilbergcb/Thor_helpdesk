"""media storage key on ticket messages

Revision ID: 202605200002
Revises: 202605200001
Create Date: 2026-05-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "202605200002"
down_revision: Union[str, None] = "202605200001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ticket_messages", sa.Column("media_storage_key", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("ticket_messages", "media_storage_key")
