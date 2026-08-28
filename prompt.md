# Vehicle Breakdown — Implementation Tasks

Context (already confirmed in codebase, do not re-explore unless something below is stale):

- Trip assignment = `DailyTripAssignment` model (`app/models/schedule_masters/daily_trip_assignment.py`), UI = "Daily Trip Plan" (`dailyTripAssignmentList.tsx`).
- Vehicle breakdown = `VehicleBreakdown` model + `VehicleBreakdownViewSet` (`app/viewsets/core_modules/daily_operations/vehicle_breakdown_viewset.py`) + `vehicleBreakdownForm.tsx` / `vehicleBreakdownList.tsx`.
- Company/project scoping already exists via `CompanyScopedViewSet.filter_queryset` (`app/viewsets/superadminmasters/company_scoped_viewset.py`).
- "Today" date filter already exists on `DailyTripAssignmentViewSet.get_queryset` via `today=true` param (`daily_trip_assignment_viewset.py:156-157`).
- Bin vs household distinction: `DailyTripCollectionPoint` (bin stops) vs `DailyTripHouseholdCollection` (household stops). Pending-stop helpers already exist: `DailyTripAssignment.pending_bin_stops()` / `pending_household_stops()` / `has_pending_stops()`.
- Re-trip is the existing pattern to mirror: `retrip_service.py` (`request_retrip`, `_create_continuation_assignment`, `approve_retrip`, `proceed_to_next_trip`), exposed via `DailyTripAssignmentViewSet.proceed_next_trip` (`POST /{unique_id}/proceed-next-trip/`), which returns `new_assignment_id` and is surfaced back on every assignment via `DailyTripAssignmentSerializer.get_retrip_info`. Frontend shows it in `dailyTripAssignmentList.tsx` `RetripCell` ("Next: {new_assignment_id}").
- Unassigned staff exists in two places: `UnassignedStaffPool` model/viewset (zone/ward-scoped pool) and ad hoc "available staff" query in `VehicleBreakdownViewSet.available_staff` (excludes staff busy on active trips for a date+role).

## Tasks

1. **Trip Assignment dropdown in Vehicle Breakdown form — scope to today + company/project.**
   In `vehicleBreakdownForm.tsx`, the trip assignment picker must only list `DailyTripAssignment` records for the current company/project and `trip_date = today`. Use the existing `today=true` query param (and existing company/project scoping, which is automatic for company users, or pass `company_id`/`project_id` for superadmin) when calling the `dailyTripAssignment` list endpoint from the form.

2. **Show unassigned staff template as replacement options.**
   When selecting a replacement driver/operator in the Vehicle Breakdown form, source options from the "unassigned staff" logic (either `UnassignedStaffPool` filtered `status=AVAILABLE`, or the `VehicleBreakdownViewSet.available_staff` endpoint — confirm which one is intended to be authoritative; they currently overlap but aren't unified) instead of/in addition to whatever is currently wired up. Confirm current wiring first, then align on one source of truth.

3. **Show remaining bin/household collection info in Vehicle Breakdown.**
   On the Vehicle Breakdown form/detail, when a trip assignment is selected, display its pending collection info:
   - If bin collection trip (`trip_collection_points.exists()` / has bin stops): show remaining **collection points** (from `pending_bin_stops()`), and let the user manually pick which ones carry over — mirrors the existing re-trip bin flow (`collection_point_ids` selection).
   - If household collection trip: auto-fetch remaining **un-collected houses** (from `pending_household_stops()`), no manual selection needed — mirrors the existing re-trip household flow (auto full carry-over).

4. **Auto-create a new Trip Assignment on breakdown report, like re-trip.**
   When a vehicle breakdown is reported/verified (via `VehicleBreakdownViewSet.verify` or on creation — confirm which step should trigger it), automatically create a continuation `DailyTripAssignment` the same way `retrip_service._create_continuation_assignment` / `approve_retrip` does, carrying over the pending bin/household stops selected/fetched in task 3, and assigning the replacement vehicle/driver/operator from the breakdown record instead of the original crew.
   - Reuse or extend `retrip_service.py` rather than duplicating its logic — e.g. add a `create_breakdown_continuation()` that shares the pending-stop/carry-over machinery with `approve_retrip()`.
   - Link the new assignment back to the `VehicleBreakdown` record (e.g. a `new_assignment` FK on `VehicleBreakdown`, mirroring `TripRetripRequest.new_assignment`).

5. **Surface the new Trip Assignment ID in the Daily Trip Plan, like re-trip.**
   Extend `DailyTripAssignmentSerializer` (mirroring `get_retrip_info`) to also expose breakdown-triggered continuation info (e.g. `get_breakdown_continuation_info` returning `{unique_id, status, new_assignment_id}`), and update `dailyTripAssignmentList.tsx` (mirroring `RetripCell`) to render "Next: {new_assignment_id}" for breakdown-triggered continuations too.

## Open questions to resolve before/while implementing
- Should breakdown-triggered continuation reuse `TripRetripRequest`, or does it need its own tracking model/field on `VehicleBreakdown`? (Leaning: new FK on `VehicleBreakdown`, since it's not a retrip request.)
- Which "unassigned staff" source (task 2) is the intended single source of truth going forward?
- Trigger point for auto-creating the continuation assignment: on breakdown report (creation) or on breakdown verify/replacement-arranged?
