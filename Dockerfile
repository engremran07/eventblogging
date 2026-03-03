# =============================================================================
# DjangoBlog — Multi-stage production Dockerfile
# Build:  docker compose build
# Run:    docker compose up -d
# =============================================================================

# ── Stage 1: Builder — compile wheels ────────────────────────────────────────
FROM python:3.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# System deps needed to compile psycopg, Pillow, etc.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libjpeg62-turbo-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/production.txt requirements/production.txt
COPY requirements/base.txt requirements/base.txt
RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements/production.txt


# ── Stage 2: Runtime — lean production image ─────────────────────────────────
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    DJANGO_ENV=production \
    PYTHONPATH=/app/apps

WORKDIR /app

# Runtime-only system deps (no compiler toolchain)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        libjpeg62-turbo \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system django \
    && adduser --system --ingroup django django

# Install pre-built wheels from builder stage
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copy application code
COPY . /app

# Create required directories
RUN mkdir -p /app/logs /app/media /app/staticfiles && \
    chown -R django:django /app/logs /app/media /app/staticfiles

# Copy and prepare entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER django

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-"]
