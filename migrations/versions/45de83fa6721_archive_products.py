"""Distinguish removed products from temporarily hidden products."""
from alembic import op
import sqlalchemy as sa
revision = "45de83fa6721"
down_revision = "34cd72ef5610"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("products", sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_products_is_archived", "products", ["is_archived"])


def downgrade():
    op.drop_index("ix_products_is_archived", table_name="products")
    op.drop_column("products", "is_archived")
