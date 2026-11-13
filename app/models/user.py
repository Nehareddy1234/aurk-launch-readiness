from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import BigInteger, Integer
from sqlalchemy.dialects.mysql import BIGINT
from app.models.types import BigIntPrimaryKey
from app.extensions import db

user_roles = db.Table("user_roles", db.Column("user_id", db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True), db.Column("role_id", db.BigInteger, db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True))
role_permissions = db.Table("role_permissions", db.Column("role_id", db.BigInteger, db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True), db.Column("permission_id", db.BigInteger, db.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True))

class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    permissions = db.relationship("Permission", secondary=role_permissions, back_populates="roles")

class Permission(db.Model):
    __tablename__ = "permissions"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    roles = db.relationship("Role", secondary=role_permissions, back_populates="permissions")

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(BigIntPrimaryKey, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(30))
    login_phone = db.Column(db.String(16), unique=True)
    google_sub = db.Column(db.String(255), unique=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    roles = db.relationship("Role", secondary=user_roles, backref="users")

    def has_permission(self, name):
        return any(p.name == name for r in self.roles for p in r.permissions)

    def has_role(self, name):
        return any(r.name == name for r in self.roles)
