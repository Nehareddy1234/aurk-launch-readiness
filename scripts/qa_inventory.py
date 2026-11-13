"""Generate local static audit inventory. Does not query any database."""
import ast
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    os.environ.update(TEST_DATABASE_URL="sqlite:///:memory:", CUSTOMER_EMAILS_ENABLED="false", MAIL_SERVER="")
    with tempfile.TemporaryDirectory(prefix="aurk-inventory-") as upload_dir:
        os.environ["UPLOAD_DIR"] = upload_dir
        from app import create_app
        from app.config import TestingConfig
        from app.extensions import db
        TestingConfig.UPLOAD_DIR = upload_dir
        app = create_app("testing")
        routes = []
        for rule in sorted(app.url_map.iter_rules(), key=lambda item: item.rule):
            view = app.view_functions[rule.endpoint]
            try:
                source = inspect.getsource(view)
            except (OSError, TypeError):
                source = ""
            permissions = re.findall(r"permission_required\(['\"]([^'\"]+)", source)
            access = "Customer login" if "@login_required" in source else "Public / conditional"
            if rule.endpoint.startswith("admin.") and rule.endpoint != "admin.login":
                access = "Admin session" + (" + " + ", ".join(permissions) if permissions else "")
            if rule.endpoint == "products.register_interest":
                access = "Coming-soon: login; out-of-stock: guest or login"
            if rule.endpoint == "community.photo":
                access = "Approved: public; other: owner or reviews.manage admin"
            if rule.endpoint in {"products.product_image", "main.media"}:
                access = "Public product: public; hidden: authorized admin"
            if rule.endpoint == "admin.root":
                access = "Admin session; redirects to dashboard"
            routes.append(dict(methods=sorted(rule.methods - {"HEAD", "OPTIONS"}), path=rule.rule,
                               endpoint=rule.endpoint, access=access))
        from sqlalchemy.orm import configure_mappers
        configure_mappers()
        models = []
        for mapper in sorted(db.Model.registry.mappers, key=lambda m: m.local_table.name):
            models.append(dict(table=mapper.local_table.name,
                columns=[f"{c.name}: {c.type}" + (" required" if not c.nullable else "") for c in mapper.columns],
                relationships=[f"{r.key} → {r.mapper.local_table.name} ({'many' if r.uselist else 'one'})" for r in mapper.relationships],
                foreign_keys=[f"{fk.parent.name} → {fk.target_fullname}; delete={fk.ondelete}" for fk in mapper.local_table.foreign_keys]))
    functions = {}
    tests = {}
    for folder, target in [(root / "app/services", functions), (root / "tests", tests)]:
        for path in sorted(folder.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            names = [f"{n.name}:{n.lineno}" for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and (target is functions or n.name.startswith("test_"))]
            if names:
                target[path.relative_to(root).as_posix()] = names
    migrations = []
    for path in (root / "migrations/versions").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        data = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for name in node.targets:
                    if isinstance(name, ast.Name) and name.id in {"revision", "down_revision"}:
                        data[name.id] = ast.literal_eval(node.value)
        if data:
            migrations.append(dict(file=path.relative_to(root).as_posix(), **data))
    artifact = root / "qa_artifacts"
    artifact.mkdir(exist_ok=True)
    inventory = dict(routes=routes, models=models, service_functions=functions, existing_tests=tests, migrations=migrations)
    (artifact / "inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    # Hash the application and deployment source so audit changes can be distinguished.
    protected = [p for folder in ("app", "migrations", "nginx") for p in (root / folder).rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts]
    protected += [root / p for p in ("wsgi.py", "gunicorn.conf.py", "requirements.txt")]
    (artifact / "application-source-hashes.json").write_text(json.dumps({p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}, indent=2), encoding="utf-8")
    lines = ["# AURK QA discovery and test inventory", "", "Local repository only. No AWS, public-site, or SMTP access.", "", "## Routes", "", "| Methods | URL | Endpoint | Access |", "|---|---|---|---|"]
    lines += [f"| {', '.join(r['methods'])} | `{r['path']}` | `{r['endpoint']}` | {r['access']} |" for r in routes]
    lines += ["", "## Models and relationships", ""]
    for model in models:
        lines += [f"### {model['table']}", "", "; ".join(model["columns"]), "", "Relationships: " + "; ".join(model["relationships"]), "", "Foreign keys: " + "; ".join(model["foreign_keys"]), ""]
    for title, group in (("Service functions", functions), ("Existing test functions", tests)):
        lines += [f"## {title}", ""]
        for path, names in group.items():
            lines += [f"- `{path}`: " + ", ".join(names)]
    lines += ["", "## Migration chain", ""]
    lines += [f"- `{m['down_revision']}` → `{m['revision']}`: `{m['file']}`" for m in sorted(migrations, key=lambda m: m["revision"])]
    lines += ["", "## Feature test inventory", "", "| Feature | Existing coverage | Audit additions / evidence |", "|---|---|---|"]
    features = [
        ("Catalog", "Public pages, sorting, pricing, gallery, availability", "Search/filter fuzzing, archived visibility, N+1 and timing, broken assets"),
        ("Cart", "Guest persistence/merge, variant identity, stock checks", "Quantity matrix, client price tampering, cross-customer mutation"),
        ("Accounts", "Login, signup, password recovery, profile/address", "Normalization, session revocation after password reset, redirect controls, rate limits"),
        ("Checkout", "COD happy path, address checks, stock changes", "Forced transaction failure, stale prices, duplicate submit, dedicated MySQL last-unit race"),
        ("Orders", "Transitions, cancellation, payment receipt", "Full invalid transition matrix and audit checks"),
        ("Admin", "Sessions, some permissions, CRUD, reports", "Every route by actor/permission and CSRF enumeration"),
        ("Emails", "Branding, retries, deduplication, sender/Reply-To", "Concurrent workers, SMTP acceptance ambiguity, injection and deleted interest"),
        ("Notify me", "Guest gate, duplicates, owner/customer alerts", "Restock limitation documented; no real SMTP"),
        ("Worn by you", "Ownership/delivery/consent/moderation", "Malicious filenames, metadata, corrupt/large photos and private URLs"),
        ("Security", "Selected CSRF, admin deny, password reset", "All mutation routes, IDOR, headers, gitignore, secret scanning"),
        ("Migrations", "Fresh SQLite upgrade", "Latest downgrade/upgrade, metadata comparison; MySQL blocked until safe URL"),
        ("Frontend", "Server-rendered HTML checks", "Approved Chromium desktop/mobile journeys, console, axe accessibility, layout"),
        ("Deployment", "Existing documentation", "Static-only config audit, no production connection"),
    ]
    lines += [f"| {a} | {b} | {c} |" for a,b,c in features]
    lines += ["", "## Configuration differences", "", "Development: DEBUG on. Production: DEBUG/TESTING off; Secure cookies default on but environment can override. Testing: in-memory SQLite by default, CSRF and limiter disabled, SMTP host blank, secret has a test default. Upload directory and email-enable flag otherwise inherit environment; the QA fixtures explicitly isolate/disable these. Dedicated MySQL must be local and have test/qa in its schema name.", "", "Per-test database tables are recreated for request tests because application code commits internally; this tests actual commit/rollback behavior rather than hiding commits inside a test transaction."]
    (root / "TEST_INVENTORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Inventory: {len(routes)} routes, {len(models)} models, {sum(map(len, tests.values()))} existing test functions")


if __name__ == "__main__":
    main()
