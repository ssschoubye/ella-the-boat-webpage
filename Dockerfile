# Production image, built by .github/workflows/build.yml and pulled by the
# home server. See deploy/DEPLOY.md for how the server runs it.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    DJANGO_DATA_DIR=/data

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Static files are baked into the image and served by WhiteNoise, so the
# container needs no writable static directory at runtime.
RUN DJANGO_SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput \
    && useradd --system --uid 10001 --no-create-home app \
    && chmod +x deploy/entrypoint.sh

EXPOSE 80

ENTRYPOINT ["deploy/entrypoint.sh"]
