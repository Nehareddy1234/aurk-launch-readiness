"""Durable welcome and order emails."""
from alembic import op
import sqlalchemy as sa
revision = "89bc27de0165"
down_revision = "78ab16cd9054"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("customer_emails",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(),"sqlite"), primary_key=True),
        sa.Column("event_key",sa.String(100),nullable=False,unique=True),
        sa.Column("kind",sa.String(30),nullable=False),
        sa.Column("user_id",sa.BigInteger(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),
        sa.Column("order_id",sa.BigInteger(),sa.ForeignKey("orders.id",ondelete="CASCADE")),
        sa.Column("recipient",sa.String(255),nullable=False),
        sa.Column("status",sa.String(20),nullable=False),
        sa.Column("attempts",sa.Integer(),nullable=False),
        sa.Column("next_attempt_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("submitted_at",sa.DateTime(timezone=True)),
        sa.Column("last_error",sa.String(200)),
        sa.CheckConstraint("kind IN ('welcome','order_received','order_confirmed')",name="ck_customer_email_kind"),
        sa.CheckConstraint("status IN ('pending','failed','submitted','skipped')",name="ck_customer_email_status"))
    op.create_index("ix_customer_emails_status","customer_emails",["status"])

def downgrade():
    op.drop_table("customer_emails")
