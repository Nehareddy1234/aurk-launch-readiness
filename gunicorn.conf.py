import os

bind = os.environ.get("GUNICORN_BIND", "127.0.0.1:8000")
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
timeout = 60
graceful_timeout = 30
max_requests = 1000
max_requests_jitter = 100
accesslog = "-"
errorlog = "-"
# Password-reset tokens appear in URL paths: never log full request URLs.
access_log_format = '%(h)s %(t)s "%(m)s" %(s)s %(b)s %(L)s'
