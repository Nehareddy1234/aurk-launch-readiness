"""Admin-managed storefront cover, banners and announcements."""
from alembic import op
import sqlalchemy as sa

revision = "a1de49fa2387"
down_revision = "90cd38ef1276"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("storefront_content", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("content", sa.JSON(), nullable=False))


def downgrade():
    op.drop_table("storefront_content")
