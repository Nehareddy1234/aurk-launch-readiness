"""Product availability and durable customer interest registrations."""
from alembic import op
import sqlalchemy as sa

revision = "56ef94ab7832"
down_revision = "45de83fa6721"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("product_status", sa.String(20), nullable=False, server_default="available"))
        batch.create_check_constraint("ck_product_status", "product_status IN ('available', 'coming_soon', 'out_of_stock')")
    bigint = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    op.create_table("product_interests",
        sa.Column("id", bigint, primary_key=True),
        sa.Column("product_id", bigint, sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", bigint, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("identity_key", sa.String(80), nullable=False),
        sa.Column("customer_name", sa.String(200)),
        sa.Column("customer_email", sa.String(254)),
        sa.Column("customer_phone", sa.String(30)),
        sa.Column("product_status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("product_id", "identity_key", name="uq_product_interest_identity"))
    for column in ("product_id", "customer_id", "customer_email"):
        op.create_index(f"ix_product_interests_{column}", "product_interests", [column])


def downgrade():
    op.drop_table("product_interests")
    with op.batch_alter_table("products") as batch:
        batch.drop_constraint("ck_product_status", type_="check")
        batch.drop_column("product_status")
