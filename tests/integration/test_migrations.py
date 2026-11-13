from sqlalchemy import text

from app.extensions import db


def test_fresh_database_migrations(app):
    """Exercise real migrations, including automatically seeded permissions."""
    with app.app_context():
        db.drop_all()

    runner = app.test_cli_runner()
    result = runner.invoke(args=["db", "upgrade"])
    assert result.exit_code == 0, result.output

    with app.app_context():
        assert db.session.execute(text("SELECT version_num FROM alembic_version")).scalar() == "d4ab72cd5610"
        assert db.session.execute(text("SELECT COUNT(*) FROM permissions WHERE name = 'orders.manage'")).scalar() == 1
        db.session.execute(text("INSERT INTO categories (name, slug, sort_order, is_active) VALUES ('Test', 'test', 0, 1)"))
        assert db.session.execute(text("SELECT id FROM categories WHERE slug = 'test'")).scalar() is not None
        db.session.rollback()

    # Starting an existing container must also tolerate an up-to-date database.
    result = runner.invoke(args=["db", "upgrade"])
    assert result.exit_code == 0, result.output
