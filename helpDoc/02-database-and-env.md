# 02 — Database and Environment

## The `.env` file — the one place settings live

`config/settings.py` reads almost nothing hard-coded. It calls
`load_dotenv()` at the top and then `os.getenv(...)` for every value that
differs between machines: the database password, the email account, the API
keys, the Django secret key.

That means:

- **`.env` is required.** Without it, Django falls back to defaults that will
  not match your machine, and you will get confusing `Access denied` errors
  from MySQL.
- **`.env` is never committed.** It is in `.gitignore`. See
  [06-gitignore-and-secrets.md](06-gitignore-and-secrets.md) for why this
  matters and what to do if it was committed by mistake.
- **`.env.example` IS committed.** It lists every key with an empty or safe
  value. It is the checklist of what a working `.env` must contain.

First thing on a fresh clone:

```bash
cp .env.example .env
# then open .env and fill in the real values
```

### What each key does

| Key | Meaning |
|---|---|
| `SECRET_KEY` | Django's signing key. Also signs JWTs (`settings_jwt.py`). Any long random string. **Changing it logs everyone out.** |
| `DJANGO_ENV` | `development` → `DEBUG=True`. Anything else (`production`) → `DEBUG=False`. |
| `DB_ENGINE` | Almost always `django.db.backends.mysql`. |
| `DB_NAME` | Database name, e.g. `iwmsdbPrivate`. |
| `DB_USER` / `DB_PASSWORD` | MySQL credentials. |
| `DB_HOST` / `DB_PORT` | `localhost` and `3306` locally. |
| `MY_API_KEY` | Shared key checked by some internal endpoints. |
| `ORS_API_KEY` | OpenRouteService — route optimisation (`app/services/openroute_service.py`). |
| `EMAIL_*` | SMTP account used to send OTP and password-reset mail. |
| `OTP_*` | OTP expiry, max attempts, resend cooldown, rate limiting. |
| `TRIP_ATTENDANCE_COOLDOWN_MINUTES` | Minimum gap between two attendance punches on one trip. |
| `ENABLE_AUTH_USER_SEEDING` | Set `false` to stop the seeder creating Django auth users. |

> **Note:** generate a fresh `SECRET_KEY` with
> `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`.

## Setting up MySQL / MariaDB

The project talks to MySQL through **PyMySQL** (a pure-Python driver, so you
do **not** need to compile `mysqlclient`).

```bash
# 1. Install the server (Debian/Ubuntu)
sudo apt install mariadb-server

# 2. Create the database and a user
sudo mysql -u root -p
```
```sql
CREATE DATABASE iwmsdbPrivate CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'iwms'@'localhost' IDENTIFIED BY 'your-password-here';
GRANT ALL PRIVILEGES ON iwmsdbPrivate.* TO 'iwms'@'localhost';
FLUSH PRIVILEGES;
```

Then put that name/user/password into your `.env`.

Use `utf8mb4` — ward, panchayat and citizen names include Tamil and Hindi
text, and the older `utf8` collation cannot store all of it.

## Migrations — the part that surprises people

Look at `.gitignore`:

```gitignore
**/migrations/*
!**/migrations/__init__.py
```

**Migration files are deliberately NOT tracked in git.** Only the empty
`__init__.py` is kept so the folder still imports.

### Why

This team chose it to avoid the constant merge conflicts you get when five
developers each generate `0042_auto_...py` on the same day against a schema
that is still changing daily. The trade-off is that **the schema is not
reproducible from git** — pulling code does not give you the tables.

### What that means for you, every single time you pull

```bash
python3 manage.py makemigrations app
python3 manage.py migrate
```

Your machine generates its own migration files from the current models, then
applies them. Two developers can end up with differently-numbered migration
files that produce the same schema. That is expected here.

### The honest warning

This works while the project is young and everyone can afford to rebuild
their local database. It does **not** give you safe production schema
changes: on a server with real data you cannot regenerate migrations from
scratch, because a generated migration knows nothing about the rows already
there. If this system goes to production with data that must survive, the
first thing to change is to start tracking `app/migrations/` in git. Raise it
with the team rather than deciding alone.

### Starting over locally

When your local schema gets into a state you cannot migrate out of, the
supported fix is to drop and rebuild — it is fast because the seeder can
recreate every row:

```bash
mysql -u root -p -e "DROP DATABASE iwmsdbPrivate; CREATE DATABASE iwmsdbPrivate CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
find . -path ./.venv -prune -o -name "__pycache__" -type d -exec rm -rf {} +
python3 manage.py makemigrations app
python3 manage.py migrate
python3 manage.py seed
```

Never do this on a server that holds real data.

## Browsing the data

- **phpMyAdmin** or any MySQL client, pointed at `DB_NAME`.
- **Django admin** at `http://localhost:8000/admin/` — needs a superuser
  (`python3 manage.py createsuperuser`, or one created by the seeder).
- **Swagger** at `http://localhost:8000/api/v1/swagger/` to poke the API
  itself rather than the tables.

Next: [03-app-structure.md](03-app-structure.md).
