FROM python:3.12-slim

# System packages:
#   libpq-dev  — headers + runtime for psycopg2 (binary wheel is self-contained but
#                libpq-dev provides the runtime lib; also needed if you ever switch to
#                the compiled psycopg2 variant)
#   libjpeg-dev — Pillow runtime support on slim images
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq-dev \
        libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps before copying code so this layer is cached independently
# of code changes — only rebuilds when requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root system user for the app process.
RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup --no-create-home appuser

# Copy entrypoint BEFORE the source-code copy and OUTSIDE /app.
# This matters for dev: the volume mount (.:/app) overwrites /app at runtime,
# so placing the entrypoint at /entrypoint.sh keeps it accessible in both
# dev (volume mount) and prod (image-only) modes.
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy the rest of the project (production use — dev will mount over this).
COPY . .

# Create the two directories the running app writes to and give the app user
# ownership. The rest of /app is read-only for appuser (source code shouldn't
# be writable at runtime).
RUN mkdir -p staticfiles media \
    && chown -R appuser:appgroup /app/staticfiles /app/media

USER appuser

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]

# Production default: collect static files then start Gunicorn.
# Dev (docker-compose.yml) overrides this with `python manage.py runserver`.
# collectstatic runs here (not at build time) so no secrets are needed during
# the image build — they are only required when the container actually starts.
CMD ["sh", "-c", "python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2"]
