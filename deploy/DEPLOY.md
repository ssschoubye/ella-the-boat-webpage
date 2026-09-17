# Deploying to Hetzner (later, once you're ready)

This is a checklist for when you move from local development to a live
Hetzner Cloud server. Nothing here needs to happen now.

1. Create a Hetzner Cloud VPS (Ubuntu, cheapest tier is enough to start),
   in a EU datacenter (Falkenstein/Nuremberg/Helsinki).
2. Point your domain's DNS A record at the server's IP address.
3. On the server: install Python, `python3-venv`, `nginx`, `postgresql`,
   and `certbot` (`python3-certbot-nginx`).
4. Create a non-root deploy user, clone your repo into its home directory.
5. Create a venv, `pip install -r requirements.txt`.
6. Create a Postgres database and user; put its connection string in
   `.env` as `DATABASE_URL` (see `.env.example`).
7. Copy `.env.example` to `.env` on the server and fill in real values,
   including a fresh `DJANGO_SECRET_KEY` and your real domain in
   `DJANGO_ALLOWED_HOSTS` / `DJANGO_CSRF_TRUSTED_ORIGINS`.
8. Run migrations and collect static files:
   ```
   DJANGO_SETTINGS_MODULE=config.settings.prod venv/bin/python manage.py migrate
   DJANGO_SETTINGS_MODULE=config.settings.prod venv/bin/python manage.py collectstatic
   ```
9. Install `deploy/gunicorn.service` as a systemd service (see comments
   in that file) and start it.
10. Install `deploy/nginx.conf` as an Nginx site (see comments in that
    file), then run Certbot to get HTTPS.
11. Visit your domain — it should now serve the Django app over HTTPS.

Ask me for a hand with any of these steps when you get there — this file
is just a map so you know what's coming.
