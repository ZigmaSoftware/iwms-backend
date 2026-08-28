# 03 — App Structure

Everything lives in `app/`. This file is a tour of each folder and how they
fit together, so you know where to put a new feature.

## The shape of one feature

Adding "Bins" to the system meant touching five folders, in this order:

```text
app/models/waste_types/bins.py            1. the table
app/serializers/.../bins.py               2. JSON in/out
app/viewsets/.../bins.py                  3. the endpoint behaviour
app/urls/base_urls.py                     4. one register_group line
app/management/commands/seeders/...       5. sample rows (optional)
tests/waste_types/test_bins.py            6. tests
```

Follow the same order for anything new. The quickest way to get it right is
to copy the nearest existing feature in the same folder and rename — the
conventions (audit fields, company/project scoping, display IDs) are easy to
miss if you start from a blank file.

## `app/models/` — the database tables

Grouped by domain, one folder per group, mirroring the URL groups:

```text
models/
├── superadmin_masters/   company, project, developer
├── common_masters/       continent, country, state
├── masters/              district, city, zone, ward, panchayat, department, ...
├── waste_types/          property, subproperty, waste type, bins
├── role_assigns/         user types
├── user_creations/       staff, staff office/personal details
├── transport_masters/    vehicle, vehicle type, fuel
├── schedule_masters/     collection points, trip plans, daily trips
├── customers/            customer creation, feedback, charge rules
├── complaint_management/ tickets, categories, SLA rules
├── grivences/            grievance records (legacy naming)
├── screen_managements/   screen and column permissions
├── notifications/        staff notifications
├── audits/               trip audits and exception logs
└── reports/              waste comparison reports
```

Two shared pieces almost every model uses, both in `app/utils/`:

- **`base_models.py`** — the base class giving every table its `unique_id`
  primary key plus the shared flags (`is_active`, `is_deleted`) and
  timestamps. The primary key is a **prefixed string**, not an auto-counting
  integer: a Continent gets `CONT-...`, and each model has its own prefix.
  This is why ids are readable in the API and stay unique across companies
  instead of colliding at `1, 2, 3`. `scoped_display_id.py` builds these.
- **`audit_mixin.py` / `common_audit.py`** — records *who* created or
  changed a row. It gets the current user from `RequestMetaMiddleware`,
  which is why that middleware must stay enabled in `config/settings.py`.

## `app/serializers/` — validation and JSON shape

Mirrors the model folders. A serializer decides which fields the API exposes,
what is required, and any cross-field rules. Shared validation helpers live
in `app/validators/` (for example `unique_name_validator.py`, which enforces
"this name must be unique *within this company*" rather than globally).

## `app/viewsets/` — the endpoints

Also mirrors the groups, plus a few audience-specific folders:

| Folder | Purpose |
|---|---|
| `masters/`, `superadminmasters/`, `core_modules/` | Standard CRUD per domain |
| `login/`, `auth/`, `citizen_login/` | Desktop login, token issue, citizen login |
| `dashboard/`, `district/`, `localbody/`, `palakad/` | Aggregated read-only dashboard data per audience |
| `operator_mobile/` | Endpoints the driver/operator mobile screens call |
| `reports/` | Report generation |
| `waste_collection_bluetooth/` | Bluetooth weighing-device capture |

Most CRUD viewsets are thin. When logic gets big it moves to
`app/services/`.

## `app/urls/` — how a viewset becomes a URL

- **`custom_router.py`** defines `GroupedRouter`, which adds
  `register_group(group, prefix, viewset)` on top of DRF's `DefaultRouter`.
  It puts the group into the URL path and gives the route a predictable
  basename, and it records the group so `/api/v1/` can render a browsable
  index of everything.
- **`base_urls.py`** is the route table — several hundred lines of
  `register_group(...)` calls plus a handful of plain `path()` entries for
  non-CRUD endpoints (`auth/forgot-password/`, `auth/verify-otp/`,
  `auth/reset-password/`, `auth/change-password/`, `permissions/assign/`).

Adding an endpoint is one line:

```python
router.register_group("masters", "villages", VillageViewSet)
# -> /api/v1/masters/villages/
```

## `app/permissions/` and `app/middleware/`

- `permissions/platform.py` — platform/superadmin level checks.
- `permissions/operator_permission.py` — what a mobile operator may do.
- `middleware/module_permission_middleware.py` — a request-level gate: does
  this user's role have access to this module at all?
- `middleware/request_meta_middleware.py` — stores the current request/user
  so the audit mixin can stamp rows.

Screen- and column-level permissions are *data*, not code: they live in the
`screen_managements` tables and are seeded by
`seeders/superadmin/screen_management/permissions.py`.

## `app/services/` — the real business logic

| File | What it does |
|---|---|
| `daily_trip_generation.py` | Turns trip *plans* into concrete daily trips |
| `daily_trip_scheduler.py` | Scheduling around those daily trips |
| `retrip_service.py` | Handling a repeated trip to the same point |
| `complaint_ticket_routing.py` | Routes a new ticket to the right team via routing/SLA rules |
| `openroute_service.py` | Calls OpenRouteService (`ORS_API_KEY`) for route optimisation |
| `staff_notification_service.py` | Builds staff notifications |
| `schema_sync_service.py` | Keeps screen-permission rows in step with the code |

## `app/utils/` — shared helpers

The ones you will reach for most:

| File | Use |
|---|---|
| `base_models.py`, `audit_mixin.py` | Base model and audit fields |
| `location_scope_mixin.py`, `hierarchy.py` | Scope queries to a user's district/zone/ward |
| `filters.py`, `pagination.py` | List filtering and paging |
| `qr.py`, `bin_qr.py`, `customer_qr.py` | QR generation for bins and customers |
| `exportExcel`-style helpers, `waste_collection_report.py` | Report building |
| `image_compress.py`, `waste_images.py` | Uploaded photo handling |
| `email_utils.py` | OTP and password-reset mail |
| `password_encryption.py` | Password handling |
| `swagger.py` | Keeps Swagger names in step with the grouped router |

## `app/signals/` and `app/apis/`

- `signals/permission_signals.py`, `signals/trip_plan_signals.py` — react to
  model saves (e.g. regenerate permissions when a screen changes).
- `apis/property_api.py` — a few function-based public endpoints for property
  and location lookups, wired directly in `config/urls.py`.

Next: [04-commands-reference.md](04-commands-reference.md).
