web: gunicorn --workers 2 --threads 2 --worker-class gthread --bind 0.0.0.0:${PORT:-5000} --access-logfile - --error-logfile - --log-level info wsgi:app
