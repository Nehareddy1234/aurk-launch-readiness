"""Add customer credentials and owner-alert retry scheduling after the live chain."""
from alembic import op
import sqlalchemy as sa

revision = "b2ef50ab3498"
down_revision = "a1de49fa2387"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("login_phone", sa.String(16)))
        batch.add_column(sa.Column("google_sub", sa.String(255)))
        batch.create_unique_constraint("uq_users_login_phone", ["login_phone"])
        batch.create_unique_constraint("uq_users_google_sub", ["google_sub"])
    op.add_column("order_notifications", sa.Column("next_attempt_at", sa.DateTime(timezone=True)))
    op.create_index("ix_order_notifications_next_attempt_at", "order_notifications", ["next_attempt_at"])


def downgrade():
    op.drop_index("ix_order_notifications_next_attempt_at", table_name="order_notifications")
    op.drop_column("order_notifications", "next_attempt_at")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("uq_users_google_sub", type_="unique")
        batch.drop_constraint("uq_users_login_phone", type_="unique")
        batch.drop_column("google_sub")
        batch.drop_column("login_phone")
