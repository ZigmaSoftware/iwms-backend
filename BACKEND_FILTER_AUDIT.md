# Backend filter audit for Stage 1

Scope: `private/iwms-backend` only. The government applications are read-only
references and were not changed.

## Baseline decision

`config/settings.py` already configures these globally:

1. `ModelFieldQueryFilter`
2. `ModelFieldSearchFilter`
3. `SerializerOrderingFilter`

Every DRF `GenericAPIView`/`ModelViewSet` therefore receives the standard stack
unless its class defines `filter_backends`. Do not add the same three-item list
to every viewset: that is redundant and creates noisy, conflict-prone diffs.

`CompanyScopedViewSet.filter_queryset()` calls DRF's filter backends first and
then applies company/project scope. A custom `get_queryset()` does not bypass
scope when the normal DRF `list()`/`get_object()` flow is retained. Keep custom
queryset joins, soft-delete predicates, hierarchy filters, and manual aliases;
the shared backends layer on top of them.

## Safe: rely on the global stack without viewset edits

These are normal list viewsets and can retain their current `get_queryset()`:

- `assets/bins_viewset.py`
- `customers/customercreation_viewset.py`, `feedback_viewset.py`,
  `userchargerule_viewset.py`, `wastecollection_viewset.py`
- `grivences/complaint_viewset.py`, `main_category_viewset.py`,
  `sub_category_viewset.py`
- `masters/block_panchayat_union_viewset.py`, `city_viewset.py`,
  `district_viewset.py`, `panchayat_viweset.py`, `ward_viewset.py`,
  `zone_viewset.py`
- `schedule_masters/alternative_staff_template_viewset.py`,
  `bin_collection_event_viewset.py`, `collection_point_viewset.py`,
  `daily_trip_assignment_viewset.py`,
  `daily_trip_household_collection_viewset.py`,
  `daily_trip_log_viewset.py`, `staff_template_viewset.py`,
  `trip_plan_collection_point_viewset.py`, `trip_plan_viewset.py`,
  `vehicle_breakdown_viewset.py`
- `transport_masters/fuel_viewset.py`, `vehicleCreation_viewset.py`,
  `vehicletypecreation_viewset.py`
- `user_creations/staff_access_configuration_viewset.py`,
  `staff_viewset.py`, `staffcreation_viewset.py`
- `waste_types/property_viewset.py`, `subproperty_viewset.py`
- `waste_collection_bluetooth/waste_type_viewset.py`
- the ordinary audit and screen-management model viewsets, subject to the
  explicit overrides below

Several dirty files currently declare the same global three-filter list
explicitly. Those declarations are behaviorally compatible but not a pattern
Stage 1 needs to repeat.

## Explicit overrides: preserve, then extend narrowly

The following classes override `filter_backends`, so they do not inherit the
global stack:

- `masters/department_viewset.py`
- `masters/designation_viewset.py`
- `masters/district_leader_viewset.py`
- `masters/panchayat_leader_viewset.py`

They have intentional relational `search_fields` and explicit
`ordering_fields`. If their frontend lists need column query parameters, safely
prepend `ModelFieldQueryFilter` while retaining DRF `SearchFilter` and
`OrderingFilter`. Do not replace their declared relational search fields with
inferred model-only search.

- `screen_managements/companyuserscreencolumnpermission_viewset.py`
- `screen_managements/companyuserscreenpermission_viewset.py`

These permission editors intentionally use only `OrderingFilter` and have
special response shapes/bulk actions. Leave them unchanged unless a specific
permission-list UI requires query filtering and has targeted API tests. If
extended, add `ModelFieldQueryFilter` before the existing ordering backend;
do not enable inferred global text search speculatively.

## Leave custom endpoints alone

Do not retrofit filter backends onto `APIView`, plain `ViewSet`, login/password,
dashboard, operator-mobile, attendance capture/recognition, Bluetooth workflow,
or other command/action endpoints. They are not generic entity list screens
and many return aggregates or hand-built payloads.

Also leave these action-heavy flows on their existing manual parameters:

- customer count and bulk-upload actions in
  `customers/customercreation_viewset.py`
- scheduler/status/approval actions in
  `schedule_masters/daily_trip_assignment_viewset.py`
- tracking/route-optimization actions in
  `schedule_masters/daily_trip_collection_point_viewset.py`
- verification/availability actions in trip-log and vehicle-breakdown
  viewsets
- permission bulk-sync/by-project actions under `screen_managements`
- staff approval/status/options actions and vehicle bulk upload

Filter backends apply automatically to normal list/retrieve flows, not to a
custom action unless that action explicitly calls `filter_queryset()`.

## Targeted defect/risk requiring separate treatment

`assets/weighbridge_viewset.py` overrides `list()` and calls
`self.get_queryset()` directly. It therefore bypasses both the global filter
stack and `CompanyScopedViewSet.filter_queryset()`, including company/project
scope. Do not merely add `filter_backends`; change the custom list to begin
with `self.filter_queryset(self.get_queryset())`, then verify its aggregate
response and pagination expectations with targeted tests.

The daily/monthly waste comparison report viewsets also override `list()` and
pass a `DailyTripLog` queryset to `self.filter_queryset()`, while their declared
serializer/queryset models are `DailyWasteComparison`/`MonthlyWeightReport`.
Company/project scope is preserved, but inferred search and serializer-derived
ordering can target the wrong model. Give these report viewsets an explicit
tailored backend list (or `filter_backends = []`) and keep their manual
date/month/hierarchy filters. Calling `self.filter_queryset()` still invokes
`CompanyScopedViewSet` tenant scoping even when the DRF backend list is empty.
Do not turn their aggregate response into a generic model list.

## Non-company-scoped model viewsets

Common geography, role assignment, administrative hierarchy, trip attendance,
unassigned staff pool, main-screen, and platform company/project management
viewsets inherit the global filter stack where they are generic viewsets.
Do not change their base class to `CompanyScopedViewSet` as part of filter
standardization; tenancy behavior is a separate authorization decision.

## Stage 1 checklist

- Preserve `CompanyScopedViewSet` and every custom `get_queryset()`.
- Avoid per-file three-backend declarations where the global setting applies.
- Preserve declared relational `search_fields`/`ordering_fields`.
- Treat hierarchy aliases (`district`, `ward_id`, etc.) as existing manual
  filters; the generic backend only handles direct concrete model fields.
- Test normal list search, direct-field query filtering, ordering, and tenant
  isolation for each module touched.
- Test custom actions separately; do not assume the list filters affect them.
