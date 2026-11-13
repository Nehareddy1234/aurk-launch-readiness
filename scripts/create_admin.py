"""Run from the project root: python -m scripts.create_admin."""
from getpass import getpass
from app import create_app
from app.extensions import db
from app.models import User, Role, Permission
from app.admin.security import ADMIN_PERMISSIONS
from app.security.validators import validate_email_address, safe_text
from werkzeug.security import generate_password_hash


def main():
    app = create_app()
    with app.app_context():
        try:
            email = validate_email_address(input("Admin email: ").strip().lower())
            if User.query.filter_by(email=email).first():
                raise ValueError("An account already exists. No changes made. Existing administrators can use password recovery.")
            first = safe_text(input("First name: "), 100)
            last = safe_text(input("Last name: "), 100)
            if not first or not last:
                raise ValueError("First and last name are required.")
            password = getpass("Password (12-1024 characters): ")
            if not 12 <= len(password) <= 1024:
                raise ValueError("Password must contain 12-1024 characters.")
            if password != getpass("Confirm password: "):
                raise ValueError("Passwords do not match.")
            user = User(email=email, first_name=first, last_name=last, password_hash=generate_password_hash(password))
            role = Role.query.filter_by(name="Super Admin").first()
            if not role:
                role = Role(name="Super Admin")
                db.session.add(role)
            for name in ADMIN_PERMISSIONS:
                permission = Permission.query.filter_by(name=name).first()
                if not permission:
                    permission = Permission(name=name)
                    db.session.add(permission)
                if permission not in role.permissions:
                    role.permissions.append(permission)
            user.roles.append(role)
            db.session.add(user)
            db.session.commit()
            print("Admin created. Sign in at /admin/login.")
        except ValueError as exc:
            db.session.rollback()
            raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
