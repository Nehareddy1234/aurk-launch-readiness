from app.extensions import db
from app.models import User


def test_register_creates_user(client):
    response = client.post(
        "/auth/register",
        data={
            "first_name": "Test",
            "last_name": "Customer",
            "email": "customer@example.com",
            "password": "StrongPassword123!",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]

    with client.application.app_context():
        user = User.query.filter_by(
            email="customer@example.com"
        ).first()

        assert user is not None
        assert user.first_name == "Test"
        assert user.last_name == "Customer"
        assert user.password_hash != "StrongPassword123!"
        assert user.is_active is True


def test_login_with_correct_password(client):
    with client.application.app_context():
        user = User(
            email="login@example.com",
            first_name="Login",
            last_name="Test",
            password_hash="",
        )

        from werkzeug.security import generate_password_hash

        user.password_hash = generate_password_hash(
            "StrongPassword123!"
        )

        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/auth/login",
        data={
            "email": "login@example.com",
            "password": "StrongPassword123!",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302


def test_login_with_wrong_password_fails(client):
    with client.application.app_context():
        from werkzeug.security import generate_password_hash

        user = User(
            email="wrong-password@example.com",
            first_name="Wrong",
            last_name="Password",
            password_hash=generate_password_hash(
                "CorrectPassword123!"
            ),
        )

        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/auth/login",
        data={
            "email": "wrong-password@example.com",
            "password": "WrongPassword123!",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Invalid email, phone number or password." in response.data


def test_inactive_user_cannot_login(client):
    with client.application.app_context():
        from werkzeug.security import generate_password_hash

        user = User(
            email="inactive@example.com",
            first_name="Inactive",
            last_name="User",
            password_hash=generate_password_hash(
                "StrongPassword123!"
            ),
            is_active=False,
        )

        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/auth/login",
        data={
            "email": "inactive@example.com",
            "password": "StrongPassword123!",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Invalid email, phone number or password." in response.data


def test_logout_requires_post(client):
    response = client.get("/auth/logout")

    assert response.status_code in (405, 302)


def test_protected_admin_requires_authentication(client):
    response = client.get("/admin", follow_redirects=False)

    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]