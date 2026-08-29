# IWMS Backend

Backend API for the **Integrated Waste Management System** — a Django 5.2 +
Django REST Framework service that powers the IWMS admin dashboard, the
operator/driver mobile screens, and the public citizen endpoints.

It handles master data (geography, waste types, vehicles, staff), trip
scheduling and daily operations, waste collection capture, complaint
ticketing, permissions, and reporting — for multiple client companies and
projects out of one deployment.

The React frontend that consumes this API lives in **`iwms-frontend`**.

---

## Quick start

Requires **Python 3.13+** and a **MySQL / MariaDB** server.

```bash
# 1. Environment
uv venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
uv sync

# 2. Settings — copy the template, then fill in real values
cp .env.example .env

# 3. Database (create it first — see helpDoc/02)
python3 manage.py makemigrations app
python3 manage.py migrate

# 4. Sample data
python3 manage.py seed

# 5. Run
python3 manage.py runserver
```

Then open:

| URL | What |
|---|---|
| `http://localhost:8000/api/v1/` | Browsable index of every API group |
| `http://localhost:8000/api/v1/swagger/` | Full interactive API docs |
| `http://localhost:8000/admin/` | Django admin |

> **New here?** Read **[helpDoc/00-START-HERE.md](helpDoc/00-START-HERE.md)**.
> It explains the whole project from scratch, assuming no prior knowledge of
> it or of Django.

---

## Documentation

The `helpDoc/` folder is the full guide. Read it in order the first time,
then use it as reference.

| # | File | Covers |
|---|---|---|
| 00 | [START HERE](helpDoc/00-START-HERE.md) | Orientation and reading order |
| 01 | [Architecture overview](helpDoc/01-architecture-overview.md) | How a request flows; every URL group |
| 02 | [Database and environment](helpDoc/02-database-and-env.md) | `.env` keys, MySQL setup, how migrations work here |
| 03 | [App structure](helpDoc/03-app-structure.md) | Tour of `app/`; where to put a new feature |
| 04 | [Commands reference](helpDoc/04-commands-reference.md) | Every command, all `seed --group` values |
| 05 | [Team workflow](helpDoc/05-team-workflow.md) | Pull → migrate → build → PR |
| 06 | [.gitignore and secrets](helpDoc/06-gitignore-and-secrets.md) | What's ignored and why; secret handling |
| 07 | [Deployment and troubleshooting](helpDoc/07-deployment-and-troubleshooting.md) | Server setup, CORS, and a symptom→fix table |
| 08 | [Unit testing guide](helpDoc/08-unit-testing-guide.md) | pytest setup, writing tests, coverage |

---

## Project layout

```text
iwms-backend/
├── manage.py               entry point for every Django command
├── config/                 project settings (not an app)
│   ├── settings.py            database, apps, CORS, email, OTP
│   ├── settings_jwt.py        token lifetime and signing
│   ├── test_settings.py       same, but SQLite in-memory for tests
│   └── urls.py                top-level routes + Swagger
├── app/                    THE app — all business code
│   ├── models/                tables, grouped by domain
│   ├── serializers/           JSON in/out validation
│   ├── viewsets/              API endpoints
│   ├── urls/                  grouped router → /api/v1/<group>/...
│   ├── permissions/           who may call what
│   ├── middleware/            per-request permission + audit context
│   ├── services/              business logic (trips, routing, ORS)
│   ├── utils/                 QR, exports, filters, scoping helpers
│   └── management/commands/   seed + backfill commands
├── tests/                  pytest suite, mirrors app structure
├── helpDoc/                full documentation (start at 00)
├── .env                    your machine's settings — NOT in git
└── .env.example            template: copy to .env
```

---

## Environment variables

All settings come from `.env`, which is **git-ignored and must stay that
way**. `.env.example` is the committed template listing every key.

```bash
cp .env.example .env
```

You must at minimum set `SECRET_KEY` and the `DB_*` values. Full table of
every key and what it does:
**[helpDoc/02-database-and-env.md](helpDoc/02-database-and-env.md)**.

> **When you add a new setting, add its key to `.env.example` in the same
> commit** — otherwise the next person's setup fails with a confusing error.

> **Never commit credentials.** Git history is permanent. See
> [helpDoc/06-gitignore-and-secrets.md](helpDoc/06-gitignore-and-secrets.md) —
> including a note on secrets already present in this repo's history that
> still need rotating.

---

## Common commands

```bash
# Migrations — run after EVERY git pull (migration files aren't in git)
python3 manage.py makemigrations app
python3 manage.py migrate

# Seed sample data
python3 manage.py seed                    # all groups, in dependency order
python3 manage.py seed --group masters    # one group

# Tests
python -m pytest tests/ -q
python -m pytest tests/ --cov=app --cov-report=term-missing -q

# Clear stale bytecode caches
find . -path ./.venv -prune -o -name "__pycache__" -type d -exec rm -rf {} +

# Full local rebuild: clean, migrate, seed, run
find . -path ./.venv -prune -o -name "__pycache__" -type d -exec rm -rf {} + \
  && python3 manage.py makemigrations app \
  && python3 manage.py migrate \
  && python3 manage.py seed \
  && python3 manage.py runserver 0.0.0.0:8000
```

Every command, and the complete list of `--group` values:
**[helpDoc/04-commands-reference.md](helpDoc/04-commands-reference.md)**.

---

## Important: migrations are not in git

`app/migrations/` is deliberately git-ignored to avoid constant
migration-numbering conflicts between developers. **Pulling code does not
give you the new tables** — you generate them on your own machine:

```bash
python3 manage.py makemigrations app && python3 manage.py migrate
```

This is the single most common source of "it works on my machine" here. The
reasoning, the trade-offs, and why this must change before production use of
real data: [helpDoc/02-database-and-env.md](helpDoc/02-database-and-env.md).

---

## Tech stack

| | |
|---|---|
| Framework | Django 5.2, Django REST Framework 3.16 |
| Database | MySQL / MariaDB via PyMySQL |
| Auth | `djangorestframework-simplejwt` — HS256, 5-hour access tokens, no refresh |
| API docs | drf-yasg (Swagger) |
| Packaging | uv (`pyproject.toml` + `uv.lock`) |
| Tests | pytest, pytest-django, pytest-cov (SQLite in-memory) |
| Serving | gunicorn |
| Other | Pillow, qrcode, requests, python-dotenv |

---

## Contributing

1. `git pull`, then `makemigrations` + `migrate`
2. Branch: `git checkout -b feature/<name>`
3. Build the feature — model → serializer → viewset → `register_group` line
   → seeder → tests ([helpDoc/03](helpDoc/03-app-structure.md))
4. `python -m pytest tests/ -q`
5. **Run `git status` and read it** — no `.env`, no `__pycache__`, no
   coverage output
6. Push and open a PR, saying which `migrate`/`seed --group` steps reviewers
   need

Full workflow: [helpDoc/05-team-workflow.md](helpDoc/05-team-workflow.md).
