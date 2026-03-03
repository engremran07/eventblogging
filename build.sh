#!/usr/bin/env bash
# =============================================================================
# Render build script — runs on every deploy
# Render detects this file automatically, or set Build Command: ./build.sh
# =============================================================================
set -o errexit

echo "==> Installing production dependencies..."
pip install --upgrade pip
pip install -r requirements/production.txt

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Build complete!"
