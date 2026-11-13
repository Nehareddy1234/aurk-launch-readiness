from itsdangerous import URLSafeTimedSerializer
from flask import current_app


def make_token(subject: str, purpose: str) -> str:
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return serializer.dumps({"subject": subject, "purpose": purpose})


def read_token(token: str, purpose: str, max_age: int):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    data = serializer.loads(token, max_age=max_age)
    if data.get("purpose") != purpose:
        raise ValueError("Invalid token purpose.")
    return data["subject"]
