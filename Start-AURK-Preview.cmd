@echo off
cd /d "%~dp0"
set "TEST_DATABASE_URL=sqlite:///:memory:"
echo Once AURK starts, open http://127.0.0.1:5000/auth/login in Chrome or Edge.
python -c "import sys; sys.path.append('.preview-deps'); from app import create_app; from app.extensions import db; app=create_app('testing'); app.config.update(TESTING=False, SECRET_KEY=__import__('secrets').token_hex(32), SESSION_COOKIE_SECURE=False, REMEMBER_COOKIE_SECURE=False, GOOGLE_CLIENT_ID='', GOOGLE_CLIENT_SECRET='', GOOGLE_REDIRECT_URI='', WTF_CSRF_ENABLED=True, TEMPLATES_AUTO_RELOAD=True); ctx=app.app_context(); ctx.push(); db.create_all(); ctx.pop(); app.run(host='127.0.0.1', port=5000, use_reloader=False)"
pause

