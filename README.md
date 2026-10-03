# mysite

A starter Django project: split settings for local development vs.
production, deployed as a container on the home server at https://ella.molder.app.

## Project layout

```
manage.py
config/                # project package
    settings/
        base.py        # shared settings
        dev.py         # local development (SQLite, DEBUG=True) — default
        prod.py        # production (SQLite under /data, DEBUG=False) — used in the container
    urls.py
    wsgi.py
core/                  # your first app — replace/extend with real features
    templates/core/home.html
deploy/                # container entrypoint
docs/                  # architecture, deployment, security, operations, ADRs
Dockerfile             # production image, built by .github/workflows/build.yml
requirements.txt
.env.example           # copy to .env and fill in
```

## Local development

Requires Python 3.10+.

```bash
cd mysite
python3 -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # then edit .env if you want, defaults are fine for local dev

python manage.py migrate
python manage.py createsuperuser   # optional, for /admin/
python manage.py runserver
```

Visit http://127.0.0.1:8000/ — you should see "Your Django project is
running". The admin panel is at http://127.0.0.1:8000/admin/.

`manage.py` defaults to `config.settings.dev`, which uses SQLite and
needs no extra setup — good for building features locally.

## Building your site

- Add new apps with `python manage.py startapp <name>`, then add the app
  to `INSTALLED_APPS` in `config/settings/base.py` and wire its URLs into
  `config/urls.py` (see how `core` is wired as an example).
- Templates go in each app's `templates/<app_name>/` folder, or in the
  project-level `templates/` folder.
- Static files (CSS/JS/images) go in `static/`.
- Define database models in each app's `models.py`, then run
  `python manage.py makemigrations` and `python manage.py migrate`.

## Deploying

Pushing to `main` builds an image and pushes it to GHCR. The home-server
repo pins its tag and runs it behind Caddy and a Cloudflare Tunnel. See
`docs/deployment.md` for the full guide, including the changes home-server needs.

## Documentation

See [`docs/`](docs/README.md) for architecture, security and sign-on,
operations, and the architecture decision records in [`docs/adr/`](docs/adr/README.md).
