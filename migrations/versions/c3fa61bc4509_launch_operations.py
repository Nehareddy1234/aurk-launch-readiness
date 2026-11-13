"""Business settings, courier settlements and complete notification events."""
from alembic import op
import sqlalchemy as sa

revision = "c3fa61bc4509"
down_revision = "b2ef50ab3498"
branch_labels = None
depends_on = None

OLD_KINDS = "kind IN ('welcome','order_received','order_confirmed','notify_interest')"
NEW_KINDS = "kind IN ('welcome','order_received','order_confirmed','order_shipped','order_delivered','order_cancelled','notify_interest','product_available')"
PK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade():
    op.create_table("store_settings", sa.Column("id",sa.Integer(),primary_key=True), sa.Column("values",sa.JSON(),nullable=False))
    op.create_table("shipments", sa.Column("id",PK,primary_key=True),
        sa.Column("order_id",sa.BigInteger(),sa.ForeignKey("orders.id",ondelete="CASCADE"),nullable=False),
        sa.Column("courier",sa.String(40),nullable=False), sa.Column("awb",sa.String(80)),
        sa.Column("status",sa.String(40),nullable=False), sa.Column("weight_grams",sa.Integer()),
        sa.Column("serviceability_confirmed_at",sa.DateTime(timezone=True)), sa.Column("dispatched_at",sa.DateTime(timezone=True)),
        sa.Column("notes",sa.String(1000)),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint("order_id",name="uq_shipments_order_id"))
    op.create_table("cod_settlements",sa.Column("id",PK,primary_key=True),
        sa.Column("order_id",sa.BigInteger(),sa.ForeignKey("orders.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("reference",sa.String(100),nullable=False),sa.Column("net_amount",sa.Numeric(12,2),nullable=False),
        sa.Column("fees",sa.Numeric(12,2),nullable=False),sa.Column("received_on",sa.Date(),nullable=False),
        sa.Column("created_by",sa.BigInteger(),sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint("order_id","reference",name="uq_cod_settlement_reference"),
        sa.CheckConstraint("net_amount >= 0 AND fees >= 0 AND net_amount + fees > 0",name="ck_cod_settlement_amount"))
    op.create_index("ix_cod_settlements_order_id","cod_settlements",["order_id"])
    with op.batch_alter_table("customer_emails") as batch:
        batch.drop_constraint("ck_customer_email_kind",type_="check")
        batch.create_check_constraint("ck_customer_email_kind",NEW_KINDS)


def downgrade():
    # Do not silently delete notification/settlement history during rollback.
    bind=op.get_bind()
    if bind.execute(sa.text("SELECT COUNT(*) FROM cod_settlements")).scalar() or bind.execute(sa.text("SELECT COUNT(*) FROM customer_emails WHERE kind IN ('order_shipped','order_delivered','order_cancelled','product_available')")).scalar():
        raise RuntimeError("Rollback would discard operational history. Restore the matching private backup instead.")
    with op.batch_alter_table("customer_emails") as batch:
        batch.drop_constraint("ck_customer_email_kind",type_="check")
        batch.create_check_constraint("ck_customer_email_kind",OLD_KINDS)
    op.drop_table("cod_settlements")
    op.drop_table("shipments")
    op.drop_table("store_settings")
