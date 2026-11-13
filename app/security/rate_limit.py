from app.extensions import limiter

LOGIN_LIMIT = "5 per minute"
REGISTER_LIMIT = "5 per hour"
PASSWORD_RESET_LIMIT = "3 per hour"
CONTACT_LIMIT = "10 per hour"
