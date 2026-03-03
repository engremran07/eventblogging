#!/bin/bash
# =============================================================================
# DjangoBlog — Docker entrypoint
# Runs migrations + collectstatic, then hands off to CMD (gunicorn)
# =============================================================================
set -e

echo "⏳ Waiting for PostgreSQL..."
until python -c "
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps'))
django.setup()
from django.db import connection
connection.ensure_connection()
" 2>/dev/null; do
    echo "  PostgreSQL not ready — retrying in 2s..."
    sleep 2
done
echo "✅ PostgreSQL is ready."

echo "⏳ Running migrations..."
python manage.py migrate --noinput

echo "⏳ Collecting static files..."
python manage.py collectstatic --noinput

echo "🚀 Starting application..."
exec "$@"
