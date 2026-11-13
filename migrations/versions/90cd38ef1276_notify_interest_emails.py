"""Queue customer Notify me acknowledgements."""
from alembic import op
import sqlalchemy as sa

revision = "90cd38ef1276"
down_revision = "89bc27de0165"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("customer_emails") as batch:
        batch.add_column(sa.Column("interest_id", sa.BigInteger(), nullable=True))
        batch.create_foreign_key("fk_customer_emails_interest", "product_interests", ["interest_id"], ["id"], ondelete="SET NULL")
        batch.drop_constraint("ck_customer_email_kind", type_="check")
        batch.create_check_constraint("ck_customer_email_kind", "kind IN ('welcome','order_received','order_confirmed','notify_interest')")


def downgrade():
    op.execute("DELETE FROM customer_emails WHERE kind = 'notify_interest'")
    with op.batch_alter_table("customer_emails") as batch:
        batch.drop_constraint("ck_customer_email_kind", type_="check")
        batch.create_check_constraint("ck_customer_email_kind", "kind IN ('welcome','order_received','order_confirmed')")
        batch.drop_constraint("fk_customer_emails_interest", type_="foreignkey")
        batch.drop_column("interest_id")
