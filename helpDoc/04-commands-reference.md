# 04 — Commands Reference

Everything you will actually type, in the order you need it. Run all of these
from the repo root (the folder holding `manage.py`), with the virtualenv
active.

## Environment setup

This project uses **[uv](https://docs.astral.sh/uv/)** to manage the
virtualenv and dependencies. `pyproject.toml` and `uv.lock` are the source of
truth; `requirements.txt` is kept in step for tools that need it.

```bash
uv venv                      # create .venv/
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows PowerShell
uv sync                      # install everything from uv.lock
```

Adding a dependency:

```bash
uv add <package>             # updates pyproject.toml AND uv.lock — commit both
```

If you are not using uv:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install --upgrade setuptools
```

Requires **Python 3.13+** (`pyproject.toml`).

Then create your `.env` — see [02-database-and-env.md](02-database-and-env.md):

```bash
cp .env.example .env
```

## Running the server

```bash
python3 manage.py runserver                  # http://127.0.0.1:8000
python3 manage.py runserver 0.0.0.0:8000     # reachable from other machines
python3 manage.py runserver 192.168.1.128:4216   # a specific LAN address
```

If you bind to a LAN address, that address must be in `ALLOWED_HOSTS` in
`config/settings.py`, and the frontend's origin must match one of the
`CORS_ALLOWED_ORIGIN_REGEXES`. See
[07-deployment-and-troubleshooting.md](07-deployment-and-troubleshooting.md).

Once it is up:

- `http://localhost:8000/api/v1/` — browsable index of every URL group
- `http://localhost:8000/api/v1/swagger/` — full API docs
- `http://localhost:8000/admin/` — Django admin

## Migrations

Remember: migration files are not in git, so you generate them yourself
(see [02](02-database-and-env.md)).

```bash
python3 manage.py makemigrations app
python3 manage.py migrate
python3 manage.py showmigrations      # what has and hasn't been applied
```

## Seeding sample data

`python3 manage.py seed` fills an empty database with a working dataset —
companies, projects, geography, staff, vehicles, trips, tickets. Without it a
fresh database has no rows and the frontend has nothing to show.

```bash
python3 manage.py seed                     # everything, in dependency order
python3 manage.py seed --group masters     # just one group
```

**Order matters.** `seed` with no arguments runs the groups in this sequence,
because each depends on the ones before it:

```text
superadmin → common-masters → masters → waste-types → role-assigns
→ user-creations → transport-masters → schedule-setup
→ schedule-operations → screen-managements → collections
→ customer-masters → complaint-ticket → reports
```

### All `--group` values

**Main groups** (these are the ones in the ordered run above):

| Group | Seeds |
|---|---|
| `superadmin` | Company, project, super-admin user, Blue Planet masters |
| `common-masters` | Continents, countries, states |
| `masters` | Districts, cities, zones, wards, panchayats, departments, designations, hierarchy, plants |
| `waste-types` | Properties, sub-properties, waste types, bins |
| `role-assigns` | User types, staff/contractor user types |
| `user-creations` | Staff office and personal records, auth users, supervisors |
| `transport-masters` | Vehicle types, vehicles, fuel, trip attendance |
| `schedule-setup` | 20 Greater Noida BP household trip plans + their customers (trip plans only) |
| `schedule-operations` | Trip attendance, supervisor user, driver wet/dry bin trips |
| `screen-managements` | Screen permissions |
| `collections` | Panchayat-, ward- and zone-wise collections |
| `customer-masters` | Customers, feedback, user charge rules |
| `complaint-ticket` | Tickets, categories, priorities, SLA and routing rules |
| `reports` | Daily and monthly waste comparison |

**Single-seeder shortcuts:**

| Group | Seeds |
|---|---|
| `blue-planet` | The Blue Planet company/project masters |
| `plant` | One Plant each for Palakkad BP and Greater Noida BP (needs `superadmin`) |
| `gno-trip-plans` | 20 Greater Noida BP household trip plans + 100 customers, trip plans only — no daily trips (needs `superadmin`) |
| `vehicle-breakdowns` | Vehicle breakdown records |
| `driver-wet-dry-bin-trips` | Driver wet/dry bin trips (needs `superadmin` + `user-creations`) |
| `retrip-demo` | A retrip demonstration dataset |
| `ticket-masters` | Complaint-ticket master data only |
| `supervisor-user` | Supervisor user (needs `user-creations` + `schedule-operations`) |
| `process-items` | Process items |

**Legacy aliases** — kept working so old notes and scripts don't break; each
points at a renamed group above:

`assets` → `waste-types` · `customers` → `customer-masters` ·
`user-creation` → `user-creations` · `grivences` → `complaint-ticket` ·
`schedule-masters` → `schedule-setup` + `schedule-operations` ·
`staff` → `user-creations` · `vehicles` → `transport-masters` ·
`platform` → `superadmin`

A wrong `--group` name is not silently ignored — the command prints the valid
list and stops.

## Backfill commands

One-off commands for repairing existing data after a schema or logic change.
Run them deliberately, not as part of routine setup:

```bash
python3 manage.py backfill_daily_trip_logs
python3 manage.py backfill_trip_log_panchayat
python3 manage.py backfill_customer_staff_ids
python3 manage.py generate_daily_trips        # create today's trips from plans
```

## Clearing Python caches

Stale `__pycache__` folders cause "I deleted that file but Django still
imports it" problems, especially after moving modules around.

```bash
# Linux / macOS
find . -path ./.venv -prune -o -name "__pycache__" -type d -exec rm -rf {} +

# Windows PowerShell
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
```

## The one-liner: full local rebuild

Clear caches, rebuild the schema, seed, and run — the command to reach for
when your local database is in a bad state:

```bash
find . -path ./.venv -prune -o -name "__pycache__" -type d -exec rm -rf {} + \
  && python3 manage.py makemigrations app \
  && python3 manage.py migrate \
  && python3 manage.py seed \
  && python3 manage.py runserver 0.0.0.0:8000
```

This assumes the database itself already exists. To drop and recreate it
first, see "Starting over locally" in
[02-database-and-env.md](02-database-and-env.md).

## Users and static files

```bash
python3 manage.py createsuperuser     # a login for /admin/
python3 manage.py collectstatic       # gather static files into staticfiles/
python3 manage.py check               # config sanity check, no DB needed
python3 manage.py shell               # interactive Django shell
```

## Tests and coverage

Full detail in [08-unit-testing-guide.md](08-unit-testing-guide.md). The
short version:

```bash
python -m pytest tests/ -q                                   # run the suite
python -m pytest tests/ --cov=app --cov-report=term-missing -q
python -m pytest tests/ --cov=app --cov-report=html -q && xdg-open htmlcov/index.html
```

Next: [05-team-workflow.md](05-team-workflow.md).
