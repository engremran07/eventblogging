# Procfile — for Heroku, Render, Railway, or any Procfile-based PaaS
web: gunicorn config.wsgi:application --workers 3 --bind 0.0.0.0:$PORT --timeout 120 --access-logfile - --error-logfile -
worker: celery -A config.celery worker -l info --concurrency 2
beat: celery -A config.celery beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
