from flask import Blueprint, jsonify
from app.extensions import db
api_bp = Blueprint("api", __name__, url_prefix="/api")

@api_bp.get("/health")
def health(): return jsonify(status="ok")


@api_bp.get("/ready")
def ready():
    """Dependency readiness without exposing configuration or exception details."""
    try:
        from app.services.runtime_health import check_runtime_dependencies
        check_runtime_dependencies()
    except Exception:
        db.session.rollback()
        return jsonify(status="unavailable"), 503
    return jsonify(status="ready")
