"""Bound product-interest owner notification retries and record uncertainty."""
from alembic import op
import sqlalchemy as sa

revision = "d4ab72cd5610"
down_revision = "c3fa61bc4509"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("product_interests", sa.Column("notification_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("product_interests", sa.Column("notification_next_attempt_at", sa.DateTime(timezone=True)))
    op.add_column("product_interests", sa.Column("notification_last_error", sa.String(200)))
    op.create_index("ix_product_interests_notification_next_attempt_at", "product_interests", ["notification_next_attempt_at"])


def downgrade():
    op.drop_index("ix_product_interests_notification_next_attempt_at", table_name="product_interests")
    with op.batch_alter_table("product_interests") as batch:
        batch.drop_column("notification_last_error")
        batch.drop_column("notification_next_attempt_at")
        batch.drop_column("notification_attempts")
