# Supervisor Trips: Active and History

The private mobile supervisor module now separates unfinished trips from closed
trip history. The Dashboard and bottom navigation count remaining trips, not all
assignments. An empty today no longer loads yesterday's completed assignments.

## Data flow

`SupervisorBloc` calls `SupervisorRepository.fetchTripWorkbench()` which reads
all pages of `GET /api/v1/schedule-operations/daily-trip-assignments/` with
`mine=true&trip_view=workbench`. `DailyTripAssignmentViewSet` retains existing
company/project and supervisor scoping. It returns today's assignments plus
older unfinished assignments. Future assignments and older completed/cancelled
assignments are excluded. The mobile app derives today's totals separately from
the remaining-work count.

History uses the same assignment endpoint with `mine=true&trip_view=history`.
It includes non-deleted Completed and Cancelled assignments, including those
without a DailyTripLog. Without date bounds it defaults to the current server
service date and previous six dates. It orders newest first and supports:

- `from_date` and `to_date`: inclusive ISO dates, validated for order.
- `status`: existing exact status values, e.g. `Completed` or `Cancelled`.
- `search`: trip ID/code, vehicle, base/substitute driver, panchayat, ward or zone.
- `retrip_only=true`: continuation assignments created by a Re-Trip approval.
- `exceptions_only=true`: service exceptions, breakdowns, Re-Trip or delay records.
- Existing `limit`/`offset` or page pagination.

Both modes add `service_date` and `as_of` to the paginated response. The mobile
app waits for every workbench page before publishing counts and rejects missing
metadata; deploy the backend before the new mobile build. Existing list calls
without `trip_view` retain their original date/status behaviour.

## Summaries and actions

Assignment serialization additionally exposes read-only actual start/end
timestamps, `trip_log_summary` and `trip_events`. These use DailyTripLog,
TripDelayReport and TripRetripRequest records. The existing collection-point and
customer-stop payloads supply outcome, weight and reason details. Verified log
status is independent of trip completion. A missing log is returned as null.

Supervisor pending Re-Trip and breakdown requests follow pagination. Breakdown
lists additionally support `mine=true`, scoped through the assignment's trip
plan supervisor, while retaining company/project restrictions.

The existing assignment approval/status actions accept optional `reason` text
and retain it in assignment remarks for audit. The status action accepts
`expected_status`; a mismatch returns 409. The status update locks the assignment
inside a transaction before validating/applying the change, preventing a stale
Scheduled cancellation from cancelling a trip that has since started.

## Operational behaviour

Completed/cancelled trips leave Active after server confirmation. Old unfinished
trips remain labelled Carried over. Collect Later stays unresolved; resolved
collections alone do not make the mobile app close a trip. Pending decisions
remain visible at zero active trips. Failed refreshes retain confirmed data and
show a warning rather than inventing an empty schedule.

History access still follows current trip-plan supervisor ownership and existing
tenancy. This change does not introduce immutable supervisor ownership snapshots
or reconstruct missing audit data. Soft-deleted records remain excluded. No
schema migration is required.

## Checks

Run `.venv/bin/python -m pytest tests/schedule_setup/test_supervisor_trip_workbench.py`.
Tests cover service dates, older unfinished trips, terminal history without logs,
filtering/pagination, supervisor ownership, invalid ranges, search, exceptions,
and stale cancellation conflicts. These use the isolated SQLite test database.
Production deployment and device verification are separate steps.
