"""Verified customer photos for the Worn by you gallery."""
from alembic import op
import sqlalchemy as sa
revision = "78ab16cd9054"
down_revision = "67fa05bc8943"
branch_labels = None
depends_on = None

def upgrade():
    key = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    op.create_table("customer_photos",
        sa.Column("id", key, primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("order_item_id", sa.BigInteger(), sa.ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False, unique=True),
        sa.Column("caption", sa.String(400), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'withdrawn')", name="ck_customer_photo_status"))
    for column in ("user_id", "product_id", "status"):
        op.create_index(f"ix_customer_photos_{column}", "customer_photos", [column])

def downgrade():
    op.drop_table("customer_photos")
