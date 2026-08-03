# IWMS Modification Prompts — Section by Section

> Target project: `/home/admin/code/IWMS/iwms-backend`
> Reference project (golden source for behaviour/UI): `/home/admin/code/TN_Iwms/iwms-government-backend`
> Framework: Django + Django REST Framework. Follow existing project conventions (CompanyScopedViewSet, TenancyReadSerializerMixin, BaseMaster, soft delete via `is_deleted`, audit mixins, `unique_id` PKs with `to_field="unique_id"`).
> After every section: run `python manage.py makemigrations && python manage.py migrate`, run project tests, and run `python manage.py check`.

---

## Section 1 — Bin Creation: Ward derived from Zone/Panchayat → Collection Point filtered by Ward

**Requirement:** In bin creation, the ward is currently shown based on the selected collection point (first ward of the collection point's `wards` M2M). Change the flow so that the ward is shown/selected based on the **zone or panchayat** first, and then the collection points shown are filtered by the selected ward.

**Target files (IWMS):**
- `app/models/assets/bins.py`
- `app/serializers/masters/waste_masters/bins_serializer.py`
- `app/viewsets/masters/waste_masters/bins_viewset.py`
- Ward / Zone / Panchayat / Collection Point list endpoints used by the bin form (verify which viewset serves ward dropdowns, e.g. masters viewsets)

**Detailed changes:**
1. `Bins` model: stop treating ward as derived only from `collection_point_id.wards.first()`. Add direct nullable FKs `zone_id` and `ward_id` (and keep `panchayat_id` if needed). Keep deriving `district_id`/`city_id` from the collection point, but allow `ward_id` to be set explicitly.
2. Serializer: expose `zone_id`/`zone_name`, `ward_id`/`ward_name`, `panchayat_id`/`panchayat_name` as writable fields (not SerializerMethodField reading the collection point). Validate that the selected collection point actually belongs to the selected ward (`collection_point.wards.filter(unique_id=ward_id).exists()`).
3. Viewset/query logic: add query-param filters `zone_id`/`zone` and `ward_id`/`ward` directly on the bin (not via `collection_point_id__wards`), plus `panchayat_id` filter. Keep backward compatibility with existing filters.
4. Ensure the ward dropdown data source returns wards filtered by zone **or** panchayat (Ward model already enforces XOR of zone/panchayat — reuse `Ward.objects.filter(zone_id=..., panchayat_id=...)`).
5. Write/update tests for the new filter + validation behaviour.

**Reference (TN_Iwms):** check `app/models/masters/ward.py`, `app/models/core_modules/schedule_setup/collection_point.py` for the zone/panchayat/ward hierarchy shape; follow the same hierarchy semantics.

---

## Section 2 — Staff Template: Remove approved_status and approved_by

**Requirement:** Remove the `approved` status and `approved by` fields from the staff template module (model, serializer, viewset, audit log, and all references).

**Target files (IWMS):**
- `app/models/schedule_masters/staff_template.py`
- `app/serializers/core_modules/schedule_setup/staff_template_serializer.py`
- `app/viewsets/core_modules/schedule_setup/staff_template_viewset.py`
- `app/models/audits/staff_template_audit_log.py` (remove/neutralise approval audit fields if present)
- `app/admin.py` and any signals/services referencing `approval_status`/`approved_by`
- Grep for `approval_status`/`approved_by`/`ApprovalStatus` across `app/` and remove/update references (especially anything that gates trip-plan auto-assign on staff-template approval).

**Detailed changes:**
1. Remove `approved_by` FK and `approval_status` field from `StaffTemplate`. Keep `status` (Active/Inactive).
2. Remove the fields from the serializer fields/read_only lists and from the viewset (including any approval actions/transitions).
3. Update the audit log model/usage so no approval columns are written.
4. Check `trip_plan` / `daily_trip_generation` / `generate_daily_trips` for any dependency on staff-template `approval_status` and remove that dependency.
5. Create migration(s) removing the columns (write `RemoveField` operations; preserve data by dropping cleanly).
6. Run tests and update any test asserting approval behaviour.

**Reference (TN_Iwms):** `app/models/core_modules/schedule_setup/staff_template.py` — verify whether TN_Iwms keeps approval on the staff template; if TN_Iwms does not gate on it, mirror that.

---

## Section 3 — Collection Point: Collection Type = Bin + Bulk only (no Household)

**Requirement:** In the collection point module, show only the collection types **bin collection** and **bulk waste collection** (do NOT show household collection for collection points). Household collection belongs to household stops, not collection points.

**Target files (IWMS):**
- `app/models/schedule_masters/collection_point.py`
- `app/serializers/core_modules/schedule_setup/collection_point_serializer.py`
- `app/viewsets/core_modules/schedule_setup/collection_point_viewset.py`
- Any dropdown/choice endpoint or hardcoded choice list for `collection_type`

**Detailed changes:**
1. Add `COLLECTION_TYPE_BULK = "bulk_waste_collection"` choice (label "Bulk Waste Collection") to `Collection_point`.
2. Restrict the choices exposed for collection point to `bin_collection` and `bulk_waste_collection` only — household remains a valid type only at the household-stop level (`DailyTripHouseholdCollection`), not on `Collection_point`. If existing collection points use household, exclude/flag them in the choice set.
3. Update serializer (choices validation) and viewset (any `collection_type` filter/dropdown) accordingly.
4. Update `daily_trip_generation` / `trip_plan` logic that reads `collection_type` so bin + bulk are handled for collection points.
5. Create migration for the new choice (no schema change needed unless you add a field), update tests.

**Reference (TN_Iwms):** `app/models/core_modules/schedule_setup/collection_point.py` (has `COLLECTION_TYPE_BULK` with `bulk_waste_collection`), and `app/models/core_modules/daily_operations/daily_trip_household_collection.py` for where household stays.

---

## Section 4 — Trip Plan: Auto-assign method + auto-add to daily trip (like TN_Iwms)

**Requirement:** Bring the trip plan module to feature-parity with TN_Iwms: same functionality, same auto-assign method, and same "auto added in the trip" behaviour (auto-generated daily trip assignment + child collection points/household stops when a trip plan is created/approved or on the nightly job).

**Target files (IWMS):**
- `app/models/schedule_masters/trip_plan.py`
- `app/models/schedule_masters/trip_plan_collection_point.py`
- `app/serializers/core_modules/schedule_setup/trip_plan_serializer.py`
- `app/viewsets/core_modules/schedule_setup/trip_plan_viewset.py`
- `app/services/daily_trip_generation.py`
- `app/services/daily_trip_scheduler.py`
- `app/management/commands/generate_daily_trips.py`
- `app/signals/trip_plan_signals.py` (if exists; otherwise create signal parity)

**Detailed changes (align with TN_Iwms `run_for_date` in `app/management/commands/generate_daily_trips.py`):**
1. `TripPlan`: ensure `is_auto_assign`, `repeat_days` (0=Monday..6=Sunday), `collection_type`, and `waste_types` (M2M) exist and behave like TN_Iwms. Keep `waste_type_ids` JSON for backward compatibility but prefer M2M where TN_Iwms uses it.
2. Auto-add on create/approve: on trip-plan creation (and on approval when `approval_status` is APPROVED), auto-generate the `DailyTripAssignment` for the plan + date and clone `TripPlanCollectionPoint` stops into `DailyTripCollectionPoint` (bin) and household/bulk stops into `DailyTripHouseholdCollection` (get_or_create — idempotent).
3. Rework `daily_trip_generation.py` to mirror TN_Iwms `run_for_date` semantics: active + `is_auto_assign=True` plans; non-force runs only approved plans + repeat-day weekday check; `force` includes not-yet-approved plans and ignores weekday. Handle bin + bulk + household stop types.
4. `generate_daily_trips` command: expose `run_for_date(target_date=None, logger=None, force=False)` and return a summary dict; scheduler should call the same path.
5. Signal parity: implement `sync_daily_assignment_stops_from_plan` / `_create_daily_household_collections` equivalents (see TN_Iwms `app/signals/trip_plan_signals.py`) so post-save of assignment copies stops automatically.
6. Viewset: add `generate_daily` manual-run action (like TN_Iwms `DailyTripAssignmentViewSet.generate_daily`).
7. Migrations for any new/changed fields; update tests.

**Reference (TN_Iwms):** `app/models/core_modules/schedule_setup/trip_plan.py`, `app/management/commands/generate_daily_trips.py`, `app/signals/trip_plan_signals.py`, `app/models/core_modules/daily_operations/daily_trip_household_collection.py`, `app/viewsets/core_modules/daily_operations/daily_trip_assignment_viewset.py`.

---

## Section 5 — Daily Trip Plan, Bin Collection Event, Waste Data Collected (like TN_Iwms)

**Requirement:** Implement the same functionality and methods for the daily trip plan (assignment), bin collection event, and waste data collected as TN_Iwms.

**Target files (IWMS):**
- `app/models/schedule_masters/daily_trip_assignment.py`
- `app/models/schedule_masters/daily_trip_collection_point.py`
- `app/models/schedule_masters/daily_trip_household_collection.py`
- `app/models/schedule_masters/bin_collection_event.py`
- `app/models/customers/wastecollection.py`
- `app/serializers/core_modules/daily_operations/*` (daily_trip_assignment, daily_trip_collection_point, daily_trip_household_collection, bin_collection_event, wastecollection)
- `app/viewsets/core_modules/daily_operations/*` (same set)
- `app/services/daily_trip_generation.py` (touched by Section 4 — coordinate)

**Detailed changes (align with TN_Iwms):**
1. `DailyTripAssignment`: add `waste_types` M2M and `household_waste_type_ids` M2M (mirror TN_Iwms); copy geo scope (ward/zone/panchayat) and staff/vehicle from the trip plan on save; keep tenant `company_id`/`project_id`. Keep `mark_completed_if_all_cps_collected` behaviour aligned with TN_Iwms (statuses Collected/Missed).
2. `DailyTripCollectionPoint`: align status vocabulary with TN_Iwms (Pending/In Progress/Collected/Missed/Collect Later as applicable) and the `mark_collected` flow.
3. `DailyTripHouseholdCollection`: ensure model/serializer/viewset parity with TN_Iwms (statuses Pending/Collected/Not Available/Collect Later, waste-type breakdown).
4. `BinCollectionEvent`: add `status` (Collected/Not Collected/Collect Later), `status_reason`, `ward`, geo scope fields, `collection_date`, and auto-copy geo from trip assignment on save (see TN_Iwms `secondary_bin_collection_event.py`).
5. `WasteCollection` (waste data collected): add `sanitary_waste`, `status` (Pending/Collected/Not Available/Collect Later), `collection_date` (user-editable), `ward`, and flat geo FKs auto-inherited from the customer via `copy_flat_geo`; auto-calculate `total_quantity`.
6. Serializers/viewsets: expose the new fields and align list/filter behaviour with TN_Iwms operator-mobile and web flows.
7. Migrations for all schema changes; run tests.

**Reference (TN_Iwms):** `app/models/core_modules/daily_operations/daily_trip_assignment.py`, `daily_trip_collection_point.py`, `daily_trip_household_collection.py`, `secondary_bin_collection_event.py`, `waste_collection.py` + their serializers/viewsets under `app/serializers/core_modules/daily_operations/` and `app/viewsets/core_modules/daily_operations/`.

---

## Section 6 — Daily Trip Log (like TN_Iwms)

**Requirement:** Implement the daily trip log module with the same functionality and methods as TN_Iwms.

**Target files (IWMS):**
- `app/models/schedule_masters/daily_trip_log.py`
- `app/serializers/core_modules/daily_operations/daily_trip_log_serializer.py`
- `app/viewsets/core_modules/daily_operations/daily_trip_log_viewset.py`
- `app/management/commands/backfill_daily_trip_logs.py` (verify parity)

**Detailed changes (align with TN_Iwms):**
1. `DailyTripLog`: keep one-to-one link to `DailyTripAssignment`; ensure `autofill_from_assignment` copies company/project, geo (zone/panchayat/ward), staff template (+ alt), driver/operator (+ extra operators), vehicle, waste type, dates, and actual start/end times.
2. Auto-weight sync: `sync_from_bin_collection_events()` (sum `BinCollectionEvent.collected_weight_kg`) and `sync_from_household_collections()` (sum `WasteCollection.total_quantity`) — only override when records exist.
3. Status flow: Draft → Submitted → Verified (read-only once Verified); block log creation for cancelled trips; require weight > 0 before submit.
4. On submit/verify, mark the linked `DailyTripAssignment` as Completed and set `actual_end_time`.
5. Align serializer/viewset (list, detail, submit, verify actions) with TN_Iwms.
6. Migrations if any field changes; run tests.

**Reference (TN_Iwms):** `app/models/core_modules/daily_operations/daily_trip_log.py`, `app/serializers/core_modules/daily_operations/daily_trip_log_serializer.py`, `app/viewsets/core_modules/daily_operations/daily_trip_log_viewset.py`.

---

## Section 7 — Frontend: Mirror every backend module change in the IWMS frontend

> Target frontend: `/home/admin/code/IWMS/iwms-frontend`
> Reference frontend (golden source for UI/behaviour): `/home/admin/code/TN_Iwms/iwms-government-frontend`
> Stack: React + TypeScript + Vite + React Router, shadcn/ui (`@/components/ui/*`), TanStack DataTable, react-i18next (`t("admin.*")` keys). API helpers live in `src/helpers/admin/index.ts` (`wardApi`, `collectionPointApi`, `tripPlanApi`, `dailyTripAssignmentApi`, `binCollectionEventApi`, `wasteCollectionApi`, `dailyTripLogApi`).
> Rule: **Each frontend agent F<n> runs in parallel with its backend agent A<n>.** F<n> mirrors the same module change in the IWMS frontend, using the TN frontend as the behaviour/UI source. F<n> should only push API-field-dependent code once the corresponding A<n> serializer contract is known (read `artifacts/A<n>.md` and `session_state.json`); UI scaffolding can start immediately from the TN reference.
> After every frontend module: run `npx eslint <changed files>`, `npx tsc --noEmit`, and `npm run build` (or the project's lint/typecheck scripts from `package.json`).

### Frontend module map (agent ↔ section ↔ files)

| Agent | Backend Section | IWMS frontend module (target) | TN frontend module (reference) |
|-------|-----------------|-------------------------------|--------------------------------|
| F1 | Section 1 — Bin Creation | `src/pages/admin/modules/masters/wasteMasters/bin/` (`BinForm.tsx`, `BinListPage.tsx`, `types.ts`) | `src/pages/admin/modules/masters/wasteMasters/bin/` (`BinForm.tsx`, `BinListPage.tsx`, `types.ts`) |
| F2 | Section 2 — Staff Template remove approval | `src/pages/admin/modules/core_modules/scheduleSetup/staffTemplate/` (`staffTemplateForm.tsx`, `staffTemplateList.tsx`, `types.ts`) + `src/pages/admin/modules/superadmin/audits/staffTemplateAudit/` | Staff template **keeps** approval in TN — F2 only **removes** the fields, do not copy TN UI here |
| F3 | Section 3 — Collection Point types | `src/pages/admin/modules/core_modules/scheduleSetup/collectionPoint/` (`CollectionPointForm.tsx`, `CollectionPointListPage.tsx`, `types.ts`) | `src/pages/admin/modules/core_modules/scheduleSetup/collectionPoint/` (same files) |
| F4 | Section 4 — Trip Plan auto-assign | `src/pages/admin/modules/core_modules/scheduleSetup/tripPlan/` (`tripPlanForm.tsx`, `tripPlanList.tsx`, `types.ts`) + `src/pages/admin/modules/core_modules/dailyOperations/dailyTripAssignment/` (auto-generate bar) | `src/pages/admin/modules/core_modules/scheduleSetup/tripPlan/` + `.../dailyOperations/dailyTripAssignment/` (same files) |
| F5 | Section 5 — Daily trip / bin collection event / waste data | `src/pages/admin/modules/core_modules/dailyOperations/` `dailyTripAssignment/`, `dailyTripCollectionPoint/`, `dailyTripHouseholdCollection/`, `binCollectionEvent/` + `src/pages/admin/modules/wasteManagementMasters/wasteCollectedData/` | `src/pages/admin/modules/core_modules/dailyOperations/` (same subfolders, incl. `wasteCollectedData/`) |
| F6 | Section 6 — Daily Trip Log | `src/pages/admin/modules/core_modules/dailyOperations/dailyTripLog/` (`dailyTripLogList.tsx`, `types.ts`) | `src/pages/admin/modules/core_modules/dailyOperations/dailyTripLog/` (incl. `collectionTime.ts`, `DailyTripLogReportPage.tsx`) |

### F1 — Bin Creation (mirror A1)

**Requirement:** Currently the bin form is collection-point-first: the ward is a read-only display auto-filled from the selected collection point's `wards` (`BinForm.tsx:468-495`). Change the flow to **zone/panchayat → ward → collection point filtered by ward** (see TN `BinForm.tsx`, which uses `wardApi` + `wardId` and filters `collectionPoints` by the selected ward).

**Detailed changes:**
1. `BinForm.tsx`: make Ward an **editable** dropdown. Load wards via `wardApi.readAll()` (TN pattern) and filter them by the selected zone **or** panchayat (`Ward` backend enforces XOR of zone/panchayat). Remove the read-only ward display block (lines ~769-803).
2. Filter the collection-point dropdown by the selected ward (only CPs whose `wards[]` contains `wardId`), not just by city/district (`collectionPointOptions`, lines ~450-464).
3. On ward change, clear and reload the collection-point selection; auto-fill panchayat/zone from the selected ward instead of the CP.
4. Send `ward_id` (and keep `zone_id`/`panchayat_id`) in the submit payload (lines ~557-571).
5. `types.ts`: add `wardApi`-driven `WardOption` type and the writable `zone_id`/`ward_id`/`panchayat_id` on `BinRecord`.
6. `BinListPage.tsx`: add `zone_id`/`ward_id` query-param filters (backend A1 adds them) alongside the existing ward/panchayat display columns.
7. Mirror the TN bin-form drop-down ordering: District → City → (Panchayat XOR Zone) → Ward → Collection Point → Bin details.

### F2 — Staff Template: remove approved_status / approved_by (mirror A2)

**Requirement:** Backend A2 is **COMPLETED** (`artifacts/A2.md`): `approval_status`, `approved_by`, `ApprovalStatus` and the audit index are removed from the API. The IWMS frontend must drop those fields now. **TN keeps approval on staff template — do NOT copy TN's approval UI; only remove.**

**Detailed changes:**
1. `types.ts`: delete `approval_status`, `approved_by` from `StaffTemplateRecord`, the list-query type, and the filter type (lines 33-34, 57, 69).
2. `staffTemplateForm.tsx`: remove `approval_status`/`approved_by` from the initial `formData` (lines 30-31), the field-visibility map (lines 41-42), the pre-fill/reset logic (lines ~320-328, 391-399), the load-from-record logic (lines ~428-434), the `approved_by`-related options memo (lines ~622-627), the submit payload (lines ~660-661), and the two form field blocks `showField("approval_status")` / `showField("approved_by")` (lines ~857-880).
3. `staffTemplateList.tsx`: remove `approval_status` from the column-visibility map (line 284), the filter initial state (line 335), the export/rowmap usage (line 456), the `showCol` list (line 618), and the column render block (lines 679-682). Remove the `approval_status` translation usage.
4. `superadmin/audits/staffTemplateAudit/`: verify the audit page does not hardcode approval columns (A2 confirmed the audit model never had them; the audit diff is model-driven). If any column/filter references approval, remove it.
5. Remove `approval_status`/`approved_by` i18n keys only if no other module uses them.

### F3 — Collection Point: Collection Type = Bin + Bulk only (mirror A3)

**Requirement:** Collection point type must expose only **bin_collection** and **bulk_waste_collection** (household stays at household-stop level). IWMS currently offers `bin_collection` / `household_collection` (form state line 185, options lines 897-904, edit normalization lines 387-389).

**Detailed changes (mirror TN `CollectionPointForm.tsx:38-40`):**
1. `CollectionPointForm.tsx`: replace the type union with `"bin_collection" | "bulk_waste_collection"` (default `"bin_collection"`). Add a `COLLECTION_TYPE_OPTIONS` constant with values `bin_collection` ("Secondary Collection Point") and `bulk_waste_collection` ("Bulk Waste Collection").
2. Update edit-mode normalization (lines 387-389) so `bulk_waste_collection` is preserved instead of falling back to `bin_collection`; remove `household_collection` handling.
3. Update the bin/stops section gating (line ~1035 `collectionType === "bin_collection"`) — bulk CPs do not get the per-bin section; align with TN.
4. `types.ts`: update `collection_type` union (line 36) and any list filter on `collection_type`.
5. `CollectionPointListPage.tsx`: verify the type column/filter reflects bin + bulk only.
6. Check `tripPlanForm.tsx` stop rows (IWMS lines 252, 528-529, 768) — household stops at trip-plan level remain valid (household collection is not removed from trip plans, only from collection-point type); do not regress F4.

### F4 — Trip Plan: auto-assign + auto-add to daily trip (mirror A4)

**Requirement:** Bring the trip-plan form/list to parity with TN: expose `is_auto_assign`, `repeat_days` (0=Monday..6=Sunday), and reflect auto-generation of the daily trip assignment on the daily-trip side.

**Detailed changes (mirror TN `tripPlanForm.tsx`):**
1. `types.ts`: add `is_auto_assign?: boolean`, `repeat_days?: number[]`, `waste_types?: { unique_id; waste_type_name }[]` (already partly present) to the record/form types; keep `waste_type_ids` for payload compatibility.
2. `tripPlanForm.tsx`: add an **Auto Assign** toggle (`setIsAutoAssign`, TN line 780) and a **Repeat Days** multi-select (`setRepeatDays`, TN line 781) shown only when auto-assign is on. Load both in edit mode (TN lines 780-781). Send `is_auto_assign` and `repeat_days` in the submit payload (TN lines 1010-1011).
3. Align the "Collection Mode" handling: when no manual stops are entered and auto-assign is on, drive bin/collection mode from the plan (TN lines ~787-794).
4. `tripPlanList.tsx`: add auto-assign/repeat-day columns + filters if the backend A4 serializer exposes them.
5. `dailyTripAssignment/dailyTripAssignmentList.tsx`: verify the "Auto Generate Daily Trips" bar (IWMS line 440) still calls the A4 `generate_daily` action with the correct params; add the manual **Generate Daily** button if A4 adds it (TN viewset `DailyTripAssignmentViewSet.generate_daily`).

### F5 — Daily Trip Plan / Bin Collection Event / Waste Data Collected (mirror A5)

**Requirement:** Mirror the A5 backend fields in the daily-operations + waste-data screens.

**Detailed changes (mirror TN):**
1. `dailyTripAssignment/`: expose `waste_types` M2M (form: `setSelectedWasteTypes` from `record.waste_types_detail`, TN form lines 293-294, 362-363) and the assignment status options (Scheduled/…/Cancelled + status column). Ensure the CP-stop and household-stop tables send `status` + `status_reason` (TN lines 740, 753-756).
2. `dailyTripCollectionPoint/`: align status badges to TN (`Pending`/`In Progress`/`Collected`/`Missed`/`Collect Later` as applicable — TN list line 20-21) and the `mark_collected` flow in the form.
3. `dailyTripHouseholdCollection/`: add `waste_types`/household waste-type breakdown + status vocabulary (`Pending`/`Collected`/`Not Available`/`Collect Later`) to list/form, mirroring TN.
4. `binCollectionEvent/`: add `status` (`Collected`/`Not Collected`/`Collect Later`), `status_reason`, `ward`, and `collection_date` to the form (TN form lines 286-293, 632-636) and list filters/columns. The `collection_date` input already exists in IWMS (line 446); wire the new status/reason/ward fields around it.
5. `wasteCollectedData/`: add `sanitary_waste` numeric input, `status` dropdown (`Pending`/`Collected`/`Not Available`/`Collect Later`), user-editable `collection_date`, and the auto-calculated `total_quantity` read-out (TN form lines 189-190, 595-596, 799-822; IWMS already computes `total_quantity` at line 293 — add the missing sanitary/status/date fields).
6. `types.ts` for each of the five modules: extend the record/form types with the new A5 fields.

### F6 — Daily Trip Log (mirror A6)

**Requirement:** Align the daily trip log screen with A6: status flow Draft → Submitted → Verified, submit/verify actions, weight>0 guard, and read-only once Verified.

**Detailed changes:**
1. `dailyTripLogList.tsx`: verify the status badge map (lines 24-26) and verify-modal flow (lines 132-174) match A6 statuses (`Draft`/`Submitted`/`Verified`). Add a **Submit** action if A6 adds one and a weight>0 client-side guard before submit.
2. Add the linked-assignment sync indicators (actual start/end time, total weight = sum of bin collection events + household collections) as read-only fields, mirroring TN.
3. `types.ts`: add `actual_start_time`/`actual_end_time`, total-weight read-only, and any `verify` action payload fields.
4. If A6 adds `DailyTripLogReportPage`/`collectionTime` parity helpers, mirror them from TN `dailyTripLog/`.

---

## Execution Order & Cross-Section Dependencies

**Backend:**
- **Independent (can start in parallel first):** Section 1 (bin), Section 2 (staff template), Section 3 (collection point).
- **Section 4 depends on:** Sections 2 & 3 outputs (staff template field removal, collection type choices).
- **Section 5 depends on:** Sections 3 & 4 outputs (collection point types, trip plan auto-assign, trip_plan_collection_point).
- **Section 6 depends on:** Section 5 outputs (bin collection event + waste collection weight sync).

**Frontend (runs in lock-step with the backend, same waves):**
- **F1, F2, F3 independent — start in Wave 1 with A1/A2/A3.** F2 can complete immediately (A2 backend already done).
- **F4 starts with A4 (Wave 2)** once F2/F3 removed/renamed the collection-type + approval fields it depends on (trip-plan stop rows reference `household_collection`; do not regress).
- **F5 starts with A5 (Wave 3)** once F3/F4 land (collection-point types, trip-plan auto-assign → daily-trip screen).
- **F6 starts with A6 (Wave 4)** once F5 lands (bin-collection-event + waste-data weight sync).
- Frontend agents must not submit API fields that the backend serializer has not yet merged; coordinate via `artifacts/F<n>.md` + `artifacts/A<n>.md`.

See `AGENT_WORKFLOW.md` for the agent-per-section assignment (backend A1–A6 + frontend F1–F6), parallel execution, dependency handoff, pause/continue and cross-CLI resume rules, plus per-agent token usage / files-modified / risk reporting.
