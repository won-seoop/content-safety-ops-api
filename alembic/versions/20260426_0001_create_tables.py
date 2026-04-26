"""create rules and moderation logs tables

Revision ID: 20260426_0001
Revises:
Create Date: 2026-04-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260426_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rule_name", sa.String(length=100), nullable=False),
        sa.Column("keyword", sa.String(length=255), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_name"),
    )
    op.create_index(op.f("ix_rules_id"), "rules", ["id"], unique=False)
    op.create_index(op.f("ix_rules_rule_name"), "rules", ["rule_name"], unique=False)

    op.create_table(
        "moderation_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("matched_rules", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_moderation_logs_content_hash"), "moderation_logs", ["content_hash"], unique=False)
    op.create_index(op.f("ix_moderation_logs_id"), "moderation_logs", ["id"], unique=False)
    op.create_index(op.f("ix_moderation_logs_user_id"), "moderation_logs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_moderation_logs_user_id"), table_name="moderation_logs")
    op.drop_index(op.f("ix_moderation_logs_id"), table_name="moderation_logs")
    op.drop_index(op.f("ix_moderation_logs_content_hash"), table_name="moderation_logs")
    op.drop_table("moderation_logs")
    op.drop_index(op.f("ix_rules_rule_name"), table_name="rules")
    op.drop_index(op.f("ix_rules_id"), table_name="rules")
    op.drop_table("rules")

