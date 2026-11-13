"""Allow coming-soon products to keep their price unannounced."""
from alembic import op
import sqlalchemy as sa

revision = "67fa05bc8943"
down_revision = "56ef94ab7832"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("hide_price", sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade():
    with op.batch_alter_table("products") as batch:
        batch.drop_column("hide_price")
