"""ticket message media columns

Revision ID: 202605200001
Revises: 202605190001
Create Date: 2026-05-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "202605200001"
down_revision: Union[str, None] = "202605190001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ticket_messages", sa.Column("media_type", sa.String(length=32), nullable=True))
    op.add_column("ticket_messages", sa.Column("media_url", sa.Text(), nullable=True))
    op.add_column("ticket_messages", sa.Column("media_mime_type", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("ticket_messages", "media_mime_type")
    op.drop_column("ticket_messages", "media_url")
    op.drop_column("ticket_messages", "media_type")
