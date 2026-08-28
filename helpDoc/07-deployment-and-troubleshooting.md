# 07 — Deployment and Troubleshooting

## First-time setup on a server

```bash
# 1. Get the code
git clone <repo-url> iwms-backend && cd iwms-backend

# 2. Python environment
uv venv && source .venv/bin/activate && uv sync

# 3. Settings — fill in real values, and set DJANGO_ENV=production
cp .env.example .env
nano .env

# 4. Database (see 02-database-and-env.md for the SQL)
python3 manage.py makemigrations app
python3 manage.py migrate

# 5. Static files and an admin login
python3 manage.py collectstatic --noinput
python3 manage.py createsuperuser

# 6. Sanity check, then run
python3 manage.py check --deploy
```

### `DJANGO_ENV` decides DEBUG

```python
ENVIRONMENT = os.getenv("DJANGO_ENV", "development")
DEBUG = ENVIRONMENT != "production"
```

On any public server, set `DJANGO_ENV=production`. With `DEBUG=True`, Django
renders a full stack trace — including settings values — to anyone who
triggers an error.

Note that `config/urls.py` only serves `MEDIA_URL` when `DEBUG` is on. Once
`DEBUG=False`, uploaded images stop being served by Django and nginx (or
whatever sits in front) must serve `media/` and `staticfiles/` directly.

## Running it for real

`runserver` is a development server — single-threaded and explicitly not for
production. Use gunicorn (already a dependency):

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

Put nginx in front to terminate TLS and serve `/static/` and `/media/` from
disk. Keep gunicorn alive with a systemd unit so it restarts on boot and on
crash.

## `ALLOWED_HOSTS` and CORS — the two settings that break access

Both live in `config/settings.py` and both are currently hard-coded lists of
IP addresses, which is the single most common cause of "the API worked
yesterday and now it doesn't".

**`ALLOWED_HOSTS`** — the hostnames/IPs Django will answer *as*. If you serve
the API on a new address, add it here or every request returns
`DisallowedHost`.

**`CORS_ALLOWED_ORIGIN_REGEXES`** — which browser origins may call the API.
This is about where the *frontend* is served from, which is a different thing
from `ALLOWED_HOSTS`. If a developer runs the frontend on a new LAN IP, their
browser gets a CORS error until a regex covers it.

Both lists have grown a long tail of individual developer machine IPs. If you
add one, add a comment saying whose it is — and remove it when that machine
is gone.

## Scheduled jobs

`cron.sh` in this repo is a **record** of the crontab on one particular
server, not something the app runs. It is per-machine, so it is git-ignored.
On that server the entries sync the dashboard, backend and frontend four
times a day (09:00, 13:00, 17:00, 21:00).

Application-level scheduling — generating the day's trips — is a Django
command, and that is the one you care about:

```bash
python3 manage.py generate_daily_trips
```

If trips are missing for today, check that job ran before assuming a bug in
the scheduler.

## Verifying a deployment

```bash
curl -i http://<host>:8000/                       # "Django backend is running!"
curl -i http://<host>:8000/api/v1/                # the grouped API index
```

Then open `http://<host>:8000/api/v1/swagger/` and try a real login through
it. A successful login returning an access token proves the database,
settings, `SECRET_KEY` and JWT config are all working together.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Table 'iwmsdb...' doesn't exist` | Pulled code, didn't migrate | `makemigrations app` then `migrate` |
| `django.db.utils.OperationalError: Access denied` | Wrong `DB_USER`/`DB_PASSWORD`, or no `.env` | Check `.env` exists and matches the MySQL user |
| `Can't connect to MySQL server` | MySQL not running, or wrong `DB_HOST`/`DB_PORT` | `sudo systemctl start mariadb`; verify host and port |
| `DisallowedHost at /` | Address missing from `ALLOWED_HOSTS` | Add it in `config/settings.py` |
| Browser: "blocked by CORS policy" | Frontend origin not matched | Add a regex to `CORS_ALLOWED_ORIGIN_REGEXES` |
| `401 Unauthorized` on every call | Token expired (5h lifetime, no refresh) | Log in again |
| Everyone logged out at once | `SECRET_KEY` changed — it signs the JWTs | Restore the key, or accept the one-time re-login |
| `ImproperlyConfigured: SECRET_KEY` | `.env` missing or `SECRET_KEY` empty | `cp .env.example .env` and fill it in |
| Deleted a file, Django still imports it | Stale `__pycache__` | Clear caches — see [04](04-commands-reference.md) |
| `makemigrations` says "no changes" but the table is wrong | Migration state out of step with models | Locally: drop and rebuild (see [02](02-database-and-env.md)) |
| Uploaded images 404 after deploy | `DEBUG=False`, so Django no longer serves `media/` | Serve `media/` from nginx |
| CSS/JS missing on `/admin/` | `collectstatic` not run, or `static/` not served | `collectstatic`, and point nginx at `staticfiles/` |
| OTP / reset mail never arrives | `EMAIL_*` wrong, or SMTP blocks the login | Verify `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD`; Gmail needs an app password |
| Route optimisation fails | `ORS_API_KEY` missing or over quota | Check the key in `.env` |
| No trips generated for today | `generate_daily_trips` didn't run | Run it manually; check the cron entry |
| Tests fail on MySQL specifics | Tests use SQLite in-memory | Expected — see [08](08-unit-testing-guide.md) |

## Reading logs

```bash
journalctl -u <your-gunicorn-unit> -f     # if running under systemd
tail -f /var/log/nginx/error.log          # nginx-level failures
```

With `DEBUG=False` Django writes tracebacks to stderr, which systemd
captures. If you see nginx return 502, the traceback is in the gunicorn
journal, not in nginx's log.

Next: [08-unit-testing-guide.md](08-unit-testing-guide.md).
