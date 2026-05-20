"""client employees and roles

Revision ID: 202605200006
Revises: 202605200005
Create Date: 2026-05-20 08:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "202605200006"
down_revision: str | None = "202605200005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employee_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "client_employees",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("whatsapp_group_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=180), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["employee_roles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["whatsapp_group_id"], ["whatsapp_groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("whatsapp_group_id", "phone", name="uq_client_employee_group_phone"),
    )
    op.create_index(
        "ix_client_employees_phone",
        "client_employees",
        ["phone"],
        unique=False,
    )
    op.add_column("whatsapp_users", sa.Column("employee_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_whatsapp_users_employee_id_client_employees",
        "whatsapp_users",
        "client_employees",
        ["employee_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_whatsapp_users_employee_id_client_employees",
        "whatsapp_users",
        type_="foreignkey",
    )
    op.drop_column("whatsapp_users", "employee_id")
    op.drop_index("ix_client_employees_phone", table_name="client_employees")
    op.drop_table("client_employees")
    op.drop_table("employee_roles")
