# IWMS — Integrated Waste Management System
### Project Documentation · as of 11 June 2026

> **One line:** IWMS is a multi-tenant platform that takes municipal waste collection end-to-end — from the household that generates waste, to the vehicle and crew that collect it, to the supervisor and admin who plan, track, and audit every gram. One Django API, one Flutter app for five field/citizen personas, one React control tower.

---

## 1. The System at a Glance

Three codebases, one brain.

| Layer | Tech | Who uses it | What it does |
|-------|------|-------------|--------------|
| **Backend** (`iwms-backend`) | Django + DRF, MySQL, JWT | Everyone (API) | Single source of truth. Multi-tenant data, auth, permissions, trip automation, reporting. |
| **Mobile** (`iwms-app`) | Flutter (BLoC, flutter_map, mobile_scanner, Bluetooth, SQLite) | Citizen, Driver, Operator, Admin, Supervisor | Five role-based apps in one binary. Field execution: scan, weigh, navigate, attend, track. |
| **Web** (`iwms-frontend`) | React 19 + TS, TanStack Query/Table, Leaflet, Recharts | Admin, Supervisor, Local Body | The control tower. Master-data CRUD, live maps, dashboards, reports, audits. |

**The spine that connects them all** — every operational record rolls up through one chain:

```
Company → Project → Zone → Ward/Panchayat → Collection Point → Bin
                                                   │
   Trip Plan (route template) ──auto──► Daily Trip Assignment ──► Daily Trip Log
        │ (vehicle + crew + waste type)        │ (today's run)         │ (what actually happened)
        └─ Trip Plan Collection Points         └─ Daily Trip CPs       └─ Bin Collection Events (weights)
```

Plan it once. The system generates today's trip automatically. The crew executes it on mobile. The weight flows back up into reports. Nobody re-keys anything.

---

## 2. The Domain Model — What the System Knows

Every record is scoped to a **Company → Project** (true multi-tenancy — two municipalities never see each other's data).

**Geography** *(the map)*
`Continent → Country → State → District → City → Zone → Ward / Panchayat`. Zones are geo-fenced polygons; Panchayats carry their own leader logins.

**People** *(the workforce & residents)*
- **Staff** (`StaffcreationOfficeDetails` + `StaffPersonalDetails`) — drivers, operators, supervisors, admins. Carries driving licence, QR badge, approval workflow, login toggle.
- **Customers** (`CustomerCreation`) — households, apartments (grouped QR), industries. Each gets a QR identity and a property type.
- **Roles** (`StaffUserType`) — Company Admin · Operator · Driver · Supervisor · Project Admin.

**Assets & waste** *(the things)*
- **Property / SubProperty** — waste *source* taxonomy (Residential → Apartment, Commercial → Shop…).
- **WasteType** — the *material* (Dry, Wet, Hazardous…).
- **Collection Point** + **Bins** — physical pickup locations and the QR-tagged containers in them.
- **Vehicles** + **Fuel** — fleet with capacity, insurance, RC, mileage.

**The trip engine** *(the verb of the whole system)*
- **StaffTemplate** — pairs a **driver + operator** (the crew).
- **TripPlan** — a route *template*: this crew + this vehicle + this waste type + these stops, repeating on chosen weekdays.
- **DailyTripAssignment** — today's concrete run, auto-spawned from the plan.
- **DailyTripCollectionPoint** — the actual stops, each marked pending → collected.
- **BinCollectionEvent** — one weight reading per bin scan.
- **DailyTripLog** — the signed-off execution record (total kg auto-summed, verified by supervisor).

**Citizen voice & oversight**
- **Complaint** (grievances, categorized, prioritized, with photo + close-out image).
- **Feedback**, **Audit logs** (login, permissions, zone-access, entity changes).

**Access control**
- Screen-level + **column-level** permissions (`CompanyUserScreenPermission`) enforced by middleware — an admin can hide not just a page but a single field from a role.

---

## 3. Authentication & Roles

- **JWT** auth. One token type resolves to four identities: **Staff**, **Customer**, **Panchayat Leader**, or platform **Super Admin**.
- Password reset is **OTP-based**; admins can force-change a staff password.
- Permissions are **data-driven**: roles → screens → actions → columns. Change a permission row and the UI reshapes itself (web polls every 10s).

| Role | Lives in | Can do |
|------|----------|--------|
| Super Admin | Web | Companies, projects, everything |
| Company Admin | Web + Mobile (M4) | Staff, fleet, trips, customers, approvals |
| Supervisor | Web + Mobile (M5) | Zone team, trip progress, verify logs |
| Driver | Mobile (M2) | Navigate route, mark stops, attendance |
| Operator | Mobile (M3) | Scan bins, weigh, log collection, attendance |
| Citizen | Mobile (M1) | Track pickup, raise complaints, see QR |
| Panchayat Leader | Web (Local Body) | Village-level dashboard |

---

## 4. The Five Mobile Modules

> One Flutter binary. On login, the user's role routes them to exactly one of these worlds.

### Module 1 — Citizen 🧍
**"Where's my garbage truck, and how do I complain?"**
A resident's window into the service. Live map of the **assigned vehicle**, geofence alerts when the truck enters their area, a **collection calendar**, waste-history charts, an AI **grievance chatbot**, and their personal **QR ID** for the operator to scan.
*Flows:* register → track vehicle live → raise & chat a complaint → get notified on pickup day.

### Module 2 — Driver 🚛
**"Drive the route, don't miss a stop."**
Turn-by-turn navigation (OpenRouteService) across all stops, mark each **collected / skipped (with reason)**, daily **attendance check-in/out**. Shares the *same trip record* as the operator, so progress is mutual and instant.

### Module 3 — Operator ♻️ *(the workhorse — currently open in IDE)*
**"Scan the bin, weigh it, log it — even offline."**
The operator drives the actual collection. [`operator_trip_home_screen.dart`](../iwms-app/lib/modules/module3_operator/presentation/screens/operator_trip_home_screen.dart) shows today's trip: panchayat, waste type, vehicle, and a card per collection point with a live **collected/total progress bar**.
- A floating **QR scanner** validates each bin against the active trip — wrong waste type, wrong panchayat, already collected, or not-in-trip are all caught with explicit errors.
- On a valid scan, a **bin sheet** opens for weight entry — manual *or* via a **Bluetooth weighbridge scale**.
- **Full offline support**: scans, weights, attendance, even login queue in **SQLite** and **sync** when the network returns. Crews in dead zones never lose data.
*Plus:* camera+GPS attendance, trip history, profile.

### Module 4 — Admin 📊
**"Watch the whole operation from my phone."**
KPI dashboard (waste collected, attendance %, vehicle status), a **live map of every active vehicle**, **leave/approval** queue, fleet health, staff management, and assignment-history drill-down.

### Module 5 — Supervisor 👷
**"Is my zone's work getting done?"**
Zone-scoped command view: today's KPIs (trips scheduled / in-progress / completed, team on duty), a live **activity & alerts** feed, per-trip progress cards, **team attendance** roster, and assignment **approve/reject**.

---

## 5. The Web Control Tower

Two faces behind one login:

**Operational Dashboard** — live ops, no data entry. Real-time **vehicle GPS map** (Leaflet), bin fill levels, household collection status, alert aggregation (complaints / weighbridge / vehicle), weighbridge anomalies, and a **Reports** suite: Monthly Waste Comparison, Monthly Distance, Trip Summary, Waste-Collected Summary — all exportable to Excel.

**Admin Portal** — the master-data engine. CRUD across **80+ entities in ~15 modules**: geography, waste types, assets/bins, customers & apartments, staff & templates, schedules & trip plans, transport & fuel, vehicle tracking, workforce reports, companies/projects, and full **audit logs**. Routes are encrypted (CryptoJS); sidebar and even table columns reshape per the logged-in user's permissions. English / Hindi / Tamil.

---

## 6. The Automation — Where It Gets Powerful

This is the part that makes IWMS more than a database with forms.

**Daily trips generate themselves.** A nightly cron runs `python manage.py generate_daily_trips`. For every **active, approved, auto-assign** TripPlan whose `repeat_days` includes today's weekday, it creates a `DailyTripAssignment` and clones every stop into `DailyTripCollectionPoint`s — pre-loaded crew, vehicle, waste type, and route. Operators wake up to a trip already waiting. *(See [`generate_daily_trips.py`](app/management/commands/generate_daily_trips.py).)*

**One trip, shared by two apps.** Because a trip hangs off the *crew template* (not an individual), the driver app and operator app resolve to the **same** assignment. When the operator marks a stop collected, the driver sees it instantly. No sync conflict, no duplicate record.

**Weight rolls up automatically.** Each bin scan writes a `BinCollectionEvent`; the `DailyTripLog.collected_weight_kg` is summed from them — which feeds the daily/monthly comparison reports with zero manual tallying.

**Everything is audited.** Logins, permission changes, zone reassignments, entity edits — all logged for compliance.

---

## 7. End-to-End Flow — A Real Example (from seeded data)

The repo ships a **deterministic demo** ([`shared_demo_trip.py`](app/management/commands/seeders/schedule_masters/shared_demo_trip.py)) that proves the full loop. Seed accounts:

| Role | Username | Password |
|------|----------|----------|
| Super Admin | `super_admin` | `Admin@123` |
| Driver | `driver_user` | `Driver123` |
| Operator | `operator_user` | `Operator123` |
| Approver/Admin | `approver_user` | `Approver123` |

> *(Demo credentials only — never ship these to production.)*

**The loop, start to finish:**

1. **Plan** *(Web admin)* — `super_admin` defines a Collection Point with QR-tagged Bins, pairs `driver_user` + `operator_user` into a **StaffTemplate**, and builds a **TripPlan**: this crew, a vehicle, "Wet Waste", a panchayat's stops, repeating Mon–Sat. `approver_user` approves it.

2. **Generate** *(Automation, 9 AM cron)* — `generate_daily_trips` sees the approved auto-assign plan, today is a repeat day → spawns **`TRIP-2026-06-NNN`** with its collection points, all `PENDING`.

3. **Execute** *(Mobile)* — `operator_user` opens the app: the trip is already there. They drive to bin #1, **scan its QR** (validated against the trip), the bin sheet opens, the **Bluetooth scale** reads **42.5 kg**, they confirm. The stop flips to `COLLECTED`, progress bar ticks to 1/5. Meanwhile `driver_user`, navigating the same route, sees that stop go green. Both punched **attendance** with a photo + GPS at start of shift.

4. **Citizen sees it** *(Mobile M1)* — a household on that route watches the vehicle approach live on their map, gets a geofence ping, and — if the truck skips them — files a **complaint** in two taps.

5. **Verify & report** *(Web/Mobile supervisor)* — at end of shift the trip is `COMPLETED`, weights auto-summed into the **DailyTripLog** (212 kg across 5 bins). The supervisor **verifies** it; it lands in the **Monthly Waste Comparison** report; the admin exports it to Excel for the municipality.

Every gram is traceable from the bin it came from to the report it lands in — that's the whole point.

---

## 8. What We Can Do With It Today

- **Run a municipality's waste collection end-to-end** without paper: plan routes, auto-dispatch crews, capture verified weights, handle citizen grievances, and report — across multiple companies/projects in isolation.
- **Hold crews accountable** with QR-bin scanning, GPS+photo attendance, and per-stop collected/skipped logs that drivers can't fake.
- **Give citizens transparency** — live truck tracking, pickup calendars, and a complaint channel with closure proof.
- **Give management control** — live fleet maps, KPI dashboards, weighbridge anomaly detection, and month-over-month analytics, all gated by field-level permissions.
- **Operate in the real world** — offline-first mobile means crews in network dead zones keep working and sync later; Bluetooth scales remove manual weight entry; multilingual web (EN/HI/TA) fits Indian municipal staff.

---

## 9. Tech Stack Reference

| | Backend | Mobile | Web |
|--|---------|--------|-----|
| Core | Django + DRF | Flutter | React 19 + TS |
| State | — | BLoC + Provider | TanStack Query, Contexts |
| Data | MySQL | SQLite (offline) + Dio | Axios + TanStack Table |
| Auth | JWT + OTP | JWT | JWT |
| Maps | — | flutter_map + ORS | Leaflet |
| Special | Swagger docs, cron automation, multi-tenant | mobile_scanner (QR), Bluetooth scale, geofence | Recharts/ApexCharts, route encryption, i18n |

---

*Generated from a full read of the three repositories. File references are clickable from the backend repo root.*
