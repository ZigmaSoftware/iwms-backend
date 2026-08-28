# 01 — Architecture Overview

## What this project is

IWMS = **Integrated Waste Management System**. This repo is the backend: a
single **Django 5.2 + Django REST Framework** project that serves a JSON API
to the React frontend (`iwms-frontend`), to operator/driver mobile screens,
and to a few public citizen endpoints.

Two things people usually get wrong on day one:

1. **It is not microservices.** There is one Django project, one database,
   one app. If you have worked on the Zigma ERP backend, forget that shape —
   there are no per-service ports or per-service databases here.
2. **`app/` is the only Django app.** Everything — masters, staff, vehicles,
   trip schedules, complaints, reports — is a folder *inside* `app/`, not a
   separate installed app. That is why `app/models/` has sub-folders instead
   of one flat `models.py`.

```text
                       ┌────────────────────────┐
   Browser / mobile ──▶ │  iwms-frontend (React) │
                       └───────────┬────────────┘
                                   │ HTTPS, JSON, Bearer token
                                   ▼
                       ┌────────────────────────┐
                       │  Django  (this repo)   │  runserver :8000
                       │  /api/v1/...           │  or gunicorn
                       └───────────┬────────────┘
                                   │ SQL
                                   ▼
                       ┌────────────────────────┐
                       │  MySQL / MariaDB       │  one database
                       └────────────────────────┘
```

## How one request travels

Take `GET /api/v1/masters/districts/`.

1. **`config/urls.py`** is the front door. It sends anything starting with
   `api/v1/` into `app/urls/base_urls.py`.
2. **`app/urls/base_urls.py`** builds the routes. It does not use plain
   `router.register()` — it uses a custom `GroupedRouter.register_group()`
   (in `app/urls/custom_router.py`). A line like:

   ```python
   router.register_group("masters", "districts", DistrictViewSet)
   ```

   produces the URL `/api/v1/masters/districts/`. The first argument is the
   **group**, the second is the **resource**. This is why the API is tidy and
   why the seeder groups have the same names — they were deliberately kept
   in sync.
3. **Middleware** runs before the view (see `config/settings.py`):
   - `ModulePermissionMiddleware` — checks the logged-in user is allowed to
     touch this module at all.
   - `RequestMetaMiddleware` — stashes the current user/request so models
     can record who created or changed a row.
4. **Authentication** — `app/authentication/jwt.py`. The frontend sends
   `Authorization: Bearer <token>`. Tokens are HS256, signed with
   `SECRET_KEY`, and last 5 hours. Refresh tokens are deliberately disabled
   (`config/settings_jwt.py`) — when a token expires the user logs in again.
5. **The viewset** (`app/viewsets/masters/...`) handles the request, applies
   permissions from `app/permissions/`, and asks the serializer for data.
6. **The serializer** (`app/serializers/`) converts model rows to JSON on the
   way out, and validates JSON on the way in.
7. **The model** (`app/models/masters/...`) is the actual database table.
8. JSON comes back up the same chain.

## The URL groups

Every endpoint lives under one of these groups. This list is the fastest map
of what the system does:

| Group | What it holds |
|---|---|
| `superadmin` | Companies and projects (the top-level tenants) |
| `common-masters` | Continents, countries, states |
| `masters` | Districts, cities, zones, wards, panchayats, departments, designations, plants, hierarchy |
| `waste-types` | Properties, sub-properties, waste types, bins |
| `role-assigns` | User types, staff user types, contractor user types |
| `user-creations` | Staff records, staff office/personal details, supervisor mapping |
| `transport-masters` | Vehicle types, vehicles, fuel |
| `schedule-setup` | Collection points, staff templates, trip plans |
| `schedule-operations` | Daily trip assignments, trip logs, bin collection events |
| `screen-managements` | Screen and column-level permissions |
| `customer-masters` | Customers, feedback, user charge rules |
| `complaint-ticket` | Tickets, categories, SLA and routing rules |
| `reports` | Daily/monthly waste comparison reports |
| `audits` | Vehicle trip audits, exception logs |
| `login`, `citizen` | Desktop login, citizen-facing login |
| `dashboard`, `district`, `localbody`, `palakad` | Dashboard aggregates per audience |
| `waste-bluetooth` | Bluetooth weighing-device capture |

You can see the live version of this list any time: start the server and open
`http://localhost:8000/api/v1/` — the custom router renders the groups as a
browsable index. Full docs with request/response shapes are at
`http://localhost:8000/api/v1/swagger/`.

## Multi-tenancy — the idea behind almost every table

Nearly every table carries a **company** and a **project**. One deployment
serves several client organisations ("Blue Planet" and its projects such as
Palakkad BP and Greater Noida BP are the seeded examples). A user is scoped
to a company/project, and `app/utils/location_scope_mixin.py` narrows every
list query so a user from one project never sees another project's rows.

When you add a new model, you almost always want the same company/project
fields and the audit mixin — copy an existing model in the same folder rather
than starting from scratch. See [03-app-structure.md](03-app-structure.md).

## Where the moving parts live

| Concern | Location |
|---|---|
| Settings, database, CORS, email | `config/settings.py` |
| Token lifetime and signing | `config/settings_jwt.py` |
| Test-only settings (SQLite) | `config/test_settings.py` |
| Route table | `app/urls/base_urls.py` |
| Grouped router | `app/urls/custom_router.py` |
| Background/business logic | `app/services/` |
| Sample data | `app/management/commands/seed.py` |
| Shared helpers (QR, export, filters) | `app/utils/` |

Next: [02-database-and-env.md](02-database-and-env.md).
