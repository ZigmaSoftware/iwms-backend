# 08 — Unit Testing Guide

## How testing is set up here

The suite uses **pytest** with **pytest-django**, configured in
`pyproject.toml` under `[tool.pytest.ini_options]`:

```toml
DJANGO_SETTINGS_MODULE = "config.test_settings"
testpaths   = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

Those naming rules matter: a file called `continent_test.py`, or a class
called `ContinentTests`, is **silently not collected**. If your new test
"passes" suspiciously fast, check the name first.

### Tests run on SQLite, not MySQL

`config/test_settings.py` imports everything from `config/settings.py` and
then replaces the database with **SQLite in-memory**. This makes the suite
fast and means it needs no MySQL server.

The trade-off: anything MySQL-specific is not covered. Raw SQL, MySQL-only
functions and collation-dependent ordering can pass here and fail in
production. Keep queries in the ORM where you can.

`test_settings.py` also loads `.env` and defines `SECRET_KEY` *before* the
wildcard import — a workaround for a circular import with
`settings_jwt.py`. Leave that ordering alone; the comment in the file
explains it.

## If you come from JUnit

| JUnit | pytest |
|---|---|
| `@Test` | any function named `test_*` |
| `class FooTest` | `class TestFoo` |
| `assertEquals(a, b)` | `assert a == b` |
| `@Before` | a fixture argument |
| `@BeforeAll` | a `scope="module"` fixture |
| `assertThrows(...)` | `with pytest.raises(...):` |

The big difference is **fixtures**. Instead of setup methods mutating shared
state, you declare what a test needs as a function argument, and pytest
builds it:

```python
def test_something(company, project):   # both come from tests/conftest.py
    ...
```

## Fixtures

`tests/conftest.py` holds the shared ones, and they are available to every
test without importing. They cover the tenant and geography chain — `company`,
`project`, and the location hierarchy — because almost every model in this
system is scoped to a company and project.

`db` is pytest-django's own fixture: taking it (directly, or via another
fixture that takes it) gives the test a database and rolls back afterwards,
so tests never leak rows into each other.

## Writing a model test — worked example

Here is a real test from the suite, `tests/common_masters/test_models/test_continent.py`:

```python
"""Unit tests for Continent model — CRUD + constraints."""
import pytest
from app.models.common_masters.continent import Continent


@pytest.mark.django_db
class TestContinentCreate:
    def test_basic_create(self):
        c = Continent.objects.create(name="Europe")
        assert c.name == "Europe"

    def test_unique_id_prefix(self):
        c = Continent.objects.create(name="Africa")
        assert c.unique_id.startswith("CONT-")

    def test_str(self):
        c = Continent.objects.create(name="Oceania")
        assert str(c) == "Oceania"


@pytest.mark.django_db
class TestContinentDefaults:
    def test_is_active_default_true(self):
        c = Continent.objects.create(name="Asia")
        assert c.is_active is True

    def test_ordering_alphabetical(self):
        Continent.objects.create(name="Zzz Land")
        Continent.objects.create(name="Aaa Land")
        names = list(Continent.objects.values_list("name", flat=True))
        assert names == sorted(names)
```

Three things to copy from it:

1. **`@pytest.mark.django_db`** on any test that touches the database.
   Without it the test errors out rather than silently skipping.
2. **Group related assertions into `Test*` classes** — create, defaults,
   constraints, soft-delete. It makes failures easy to read.
3. **Cover the conventions, not just the happy path.** Every model here has a
   prefixed `unique_id` primary key (`CONT-...`), an `is_active` default and
   an `is_deleted` soft-delete flag. Those are exactly the things a
   copy-pasted new model gets wrong, so assert them.

Mirror the app's layout when placing the file:
`app/models/masters/village.py` → `tests/masters/test_models/test_village.py`.

## Running the suite

```bash
python -m pytest tests/ -q                       # everything
python -m pytest tests/common_masters/ -q        # one folder
python -m pytest tests/common_masters/test_models/test_continent.py -q
python -m pytest tests/ -k "continent" -q        # by name
python -m pytest tests/ -x                       # stop at first failure
python -m pytest tests/ -q --tb=long             # full tracebacks
```

`addopts` in `pyproject.toml` already applies `-q`, `--tb=short` and
`--strict-markers`. **`--strict-markers` means a typo'd marker is an error,
not a warning** — `@pytest.mark.djano_db` fails the run instead of quietly
doing nothing. That is deliberate.

`tests/scheduler_guard_plugin.py` is loaded as a plugin (also via `addopts`);
it guards against the trip scheduler firing during tests.

## Coverage

Configured in `pyproject.toml` under `[tool.coverage.*]`. Migrations, admin,
the seeder commands and signals are excluded — generated or
integration-shaped code that unit tests are not meant to cover.

```bash
# Terminal, with the uncovered line numbers
python -m pytest tests/ --cov=app --cov-report=term-missing -q

# Browsable HTML report -> htmlcov/index.html
python -m pytest tests/ --cov=app --cov-report=html -q && xdg-open htmlcov/index.html

# XML, for CI tools
python -m pytest tests/ --cov=app --cov-report=xml -q
```

All three outputs (`htmlcov/`, `coverage.xml`, `.coverage`) are git-ignored —
they are regenerated on every run, so never commit them.

The HTML report is the useful one: open `htmlcov/index.html`, click a module,
and unexecuted lines are highlighted in red. That is the fastest way to find
which branch of a viewset nothing exercises.

## What is worth testing here

Highest value first:

1. **Model constraints** — uniqueness within a company, defaults,
   soft-delete, the `unique_id` prefix.
2. **Serializer validation** — that bad input is rejected with a clear
   message, not a 500.
3. **Permission and scoping** — that a user from project A cannot read
   project B's rows. This is the one where a bug is a data leak, and it is
   worth testing even though it is more setup.
4. **Services** — `daily_trip_generation`, `complaint_ticket_routing` and
   friends hold the real logic and the real edge cases.

Back to [00-START-HERE.md](00-START-HERE.md).
