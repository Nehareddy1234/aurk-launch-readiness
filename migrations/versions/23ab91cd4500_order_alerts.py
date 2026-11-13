"""Persistent order alerts and owner order management permission.

Revision ID: 23ab91cd4500
Revises: 11b8ff211bcb
"""
from alembic import op
import sqlalchemy as sa

revision = "23ab91cd4500"
down_revision = "11b8ff211bcb"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("order_notifications",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("order_id", sa.BigInteger(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(255)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("order_id", "channel", name="uq_order_notification_channel"))
    connection = op.get_bind()
    permissions = sa.table("permissions", sa.column("id", sa.BigInteger()), sa.column("name", sa.String()))
    roles = sa.table("roles", sa.column("id", sa.BigInteger()), sa.column("name", sa.String()))
    links = sa.table("role_permissions", sa.column("role_id", sa.BigInteger()), sa.column("permission_id", sa.BigInteger()))
    permission_id = connection.scalar(sa.select(permissions.c.id).where(permissions.c.name == "orders.manage"))
    if permission_id is None:
        connection.execute(permissions.insert().values(name="orders.manage"))
        permission_id = connection.scalar(sa.select(permissions.c.id).where(permissions.c.name == "orders.manage"))
    for role_id in connection.scalars(sa.select(roles.c.id).where(roles.c.name == "Super Admin")):
        existing = connection.scalar(sa.select(links.c.role_id).where(links.c.role_id == role_id, links.c.permission_id == permission_id))
        if existing is None:
            connection.execute(links.insert().values(role_id=role_id, permission_id=permission_id))


def downgrade():
    op.drop_table("order_notifications")
    # Preserve the permission: administrators may have assigned it to roles.
