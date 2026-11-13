"""Revocable admin sessions and workspace permissions.

Revision ID: 34cd72ef5610
Revises: 23ab91cd4500
"""
from alembic import op
import sqlalchemy as sa

revision = "34cd72ef5610"
down_revision = "23ab91cd4500"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("admin_sessions",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("password_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False))
    op.create_index("ix_admin_sessions_user_id", "admin_sessions", ["user_id"])
    op.create_index("ix_admin_sessions_expires_at", "admin_sessions", ["expires_at"])
    connection = op.get_bind()
    permissions = sa.table("permissions", sa.column("id", sa.BigInteger()), sa.column("name", sa.String()))
    roles = sa.table("roles", sa.column("id", sa.BigInteger()), sa.column("name", sa.String()))
    links = sa.table("role_permissions", sa.column("role_id", sa.BigInteger()), sa.column("permission_id", sa.BigInteger()))
    # Preserve all existing users and assignments. Only the established owner role
    # receives new capabilities automatically; restricted Admin roles do not.
    names = ("dashboard.view", "products.view", "products.create", "products.update",
        "products.delete", "orders.manage", "customers.manage", "inventory.manage",
        "coupons.manage", "reviews.manage", "analytics.view", "settings.manage")
    owner_roles = list(connection.scalars(sa.select(roles.c.id).where(roles.c.name == "Super Admin")))
    for name in names:
        permission_id = connection.scalar(sa.select(permissions.c.id).where(permissions.c.name == name))
        if permission_id is None:
            connection.execute(permissions.insert().values(name=name))
            permission_id = connection.scalar(sa.select(permissions.c.id).where(permissions.c.name == name))
        for role_id in owner_roles:
            existing = connection.scalar(sa.select(links.c.role_id).where(links.c.role_id == role_id, links.c.permission_id == permission_id))
            if existing is None:
                connection.execute(links.insert().values(role_id=role_id, permission_id=permission_id))


def downgrade():
    op.drop_table("admin_sessions")
    # Retain permissions that may since have been assigned to other roles.
