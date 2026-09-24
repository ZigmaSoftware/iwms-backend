"""
Generic cascading soft-delete with STRING_FK_CASCADE_RELATIONS for CharField-based relations.

A model that inherits BaseMaster can declare:

    CASCADE_SOFT_DELETE = ("wards", "block_panchayat_unions")

— a tuple of reverse-relation accessor names on that model. When an
instance is soft-deleted, every related object reachable through those
accessors is soft-deleted too, recursively (a child's own
CASCADE_SOFT_DELETE is walked in turn), deduplicated by (model, pk), and
applied as one bulk UPDATE per model touched inside a single transaction.

BaseMaster.delete() calls cascade_soft_delete() itself, so any model that
inherits it and declares CASCADE_SOFT_DELETE gets this for free.
"""
from collections import defaultdict
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist


_AUDIT_RELATED_NAMES = {"created_by", "updated_by"}


def _lazy_model(dotted_path):
    """Import a model lazily by dotted path (avoids import-order issues)."""
    import importlib

    module_path, class_name = dotted_path.rsplit(".", 1)
    return getattr(importlib.import_module(module_path), class_name)


# {(dotted declaring-model path, relation_name): (dotted child-model path, filter_field)}
# Populated for every CASCADE_SOFT_DELETE relation name that used to be a
# real reverse-FK/OneToOne accessor before the child's own field was
# converted from ForeignKey to a plain `<field>_id` CharField holding the
# parent's unique_id.
STRING_FK_CASCADE_RELATIONS = {}


def _register(declaring_path, relation_name, child_path, filter_field):
    STRING_FK_CASCADE_RELATIONS[(declaring_path, relation_name)] = (child_path, filter_field)


def _model_path(model):
    return f"{model.__module__}.{model.__qualname__}"


def _resolve_related_manager(model, obj, rel_name):
    """Return an object with `.all()` (an iterable of children) for
    `obj.<rel_name>`, whether that's a real Django reverse-FK/M2M/OneToOne
    accessor or a registered string-FK cascade relation. Returns None if
    neither resolves."""
    try:
        related = getattr(obj, rel_name, None)
    except ObjectDoesNotExist:
        # Reverse OneToOne accessor raises when no related row exists.
        return None
    if related is not None:
        return related

    entry = STRING_FK_CASCADE_RELATIONS.get((_model_path(model), rel_name))
    if entry is None:
        return None
    child_path, filter_field = entry
    child_model = _lazy_model(child_path)
    return child_model.objects.filter(**{filter_field: obj.pk})


def _related_objects(instance, accessor_name):
    """Normalizes a declared accessor to a list of objects.

    Most accessors are reverse FK/M2M managers (`.all()`). A reverse
    one-to-one accessor instead returns a single object directly, and
    raises <Model>.DoesNotExist if nothing is linked.
    """
    related = getattr(instance, accessor_name, None)
    if related is None:
        return []

    if hasattr(related, "all"):
        return list(related.all())

    # Reverse one-to-one: `related` is already the object itself, but
    # accessing it can have raised DoesNotExist before we got here — that
    # happens inside the getattr above and is handled by the caller.
    return [related]


def _get_related_safely(instance, accessor_name):
    try:
        return _related_objects(instance, accessor_name)
    except Exception as exc:
        # Reverse one-to-one accessors raise <Model>.DoesNotExist when
        # nothing is linked. Any other exception type is a real bug, not
        # an absent relation, and should not be swallowed.
        if exc.__class__.__name__ == "DoesNotExist":
            return []
        raise


def _declared_cascade_accessors(instance):
    return tuple(getattr(instance, "CASCADE_SOFT_DELETE", ()))


def _cascade_accessors(instance):
    return _declared_cascade_accessors(instance)


def _collect_cascade_graph(instance, seen):
    """Depth-first walk of instance's CASCADE_SOFT_DELETE graph.

    `seen` maps model class -> set of pks already visited, so a row
    reachable via two different paths is only ever queued once.
    """
    key = (type(instance), instance.pk)
    model_seen = seen.setdefault(type(instance), set())
    if instance.pk in model_seen:
        return
    model_seen.add(instance.pk)

    for accessor_name in _cascade_accessors(instance):
        related = _resolve_related_manager(type(instance), instance, accessor_name)
        if related is None:
            continue
        if hasattr(related, "all"):
            # Reverse FK / M2M manager, or our registry QuerySet.
            for child in related.all().iterator():
                _collect_cascade_graph(child, seen)
        else:
            # Reverse OneToOne accessor — a single model instance.
            _collect_cascade_graph(related, seen)


def collect_cascade_targets(instance):
    """Returns {model_class: set(pks)} for instance's whole cascade graph, not including instance itself."""
    seen = {}
    _collect_cascade_graph(instance, seen)
    root_seen = seen.get(type(instance))
    if root_seen is not None:
        root_seen.discard(instance.pk)
        if not root_seen:
            seen.pop(type(instance), None)
    return {model: pks for model, pks in seen.items() if pks}


@transaction.atomic
def cascade_soft_delete(instance, updated_by=None):
    """Soft-deletes instance and every object in its CASCADE_SOFT_DELETE graph.

    Applies as one bulk UPDATE per model class touched (plus one for
    instance's own model), stamping updated_by when the model has that
    field. instance itself is left as a normal Python object the caller
    can still use afterward — only its DB row is updated via the bulk
    query, mirroring every other model's rows.
    """
    targets = collect_cascade_targets(instance)

    all_models = defaultdict(set)
    all_models[type(instance)].add(instance.pk)
    for model, pks in targets.items():
        all_models[model].update(pks)

    for model, pks in all_models.items():
        update_fields = {}
        if _model_has_field(model, "is_deleted"):
            update_fields["is_deleted"] = True
        if _model_has_field(model, "is_active"):
            update_fields["is_active"] = False
        if _model_has_field(model, "active_status"):
            update_fields["active_status"] = False
        if updated_by is not None and _model_has_field(model, "updated_by_id"):
            update_fields["updated_by_id"] = _account_id(updated_by)
        if update_fields:
            model.objects.filter(pk__in=pks, is_deleted=False).update(**update_fields)

    instance.is_deleted = True
    if _model_has_field(type(instance), "is_active"):
        instance.is_active = False
    if _model_has_field(type(instance), "active_status"):
        instance.active_status = False
    if updated_by is not None and _model_has_field(type(instance), "updated_by_id"):
        instance.updated_by_id = _account_id(updated_by)


def _account_id(updated_by):
    """`updated_by` is a string account_id at every remaining call site, but
    accept an Account instance too so a caller mid-migration to the new
    convention doesn't silently write the wrong value."""
    return getattr(updated_by, "account_id", updated_by)


def _model_has_field(model, field_name):
    return any(f.name == field_name for f in model._meta.fields)


# ============================================================
# STRING_FK_CASCADE_RELATIONS Registration
# Register all CharField-based reverse relations for cascade soft delete
# ============================================================

# Common imports
_COMPANY = "app.models.superadmin_masters.company.Company"
_PROJECT = "app.models.superadmin_masters.project.Project"
_DISTRICT = "app.models.masters.district.District"
_CITY = "app.models.masters.city.City"
_ZONE = "app.models.masters.zone.Zone"
_WARD = "app.models.masters.ward.Ward"
_PANCHAYAT = "app.models.masters.panchayat.Panchayat"
_BLOCK_PANCHAYAT_UNION = "app.models.masters.block_panchayat_union.BlockPanchayatUnion"
_STATE = "app.models.superadmin.common_masters.state.State"
_COUNTRY = "app.models.superadmin.common_masters.country.Country"
_CONTINENT = "app.models.superadmin.common_masters.continent.Continent"
_STAFF_CREATION = "app.models.superadmin.staff_management.staffcreation.StaffcreationOfficeDetails"
_DEPARTMENT = "app.models.superadmin.staff_management.department.Department"
_DESIGNATION = "app.models.superadmin.staff_management.designation.Designation"
_STAFF_TEMPLATE = "app.models.core_modules.schedule_setup.staff_template.StaffTemplate"
_ALT_STAFF_TEMPLATE = "app.models.core_modules.schedule_setup.alternative_staff_template.AlternativeStaffTemplate"
_TRIP_PLAN = "app.models.core_modules.schedule_setup.trip_plan.TripPlan"
_COLLECTION_POINT = "app.models.core_modules.schedule_setup.collection_point.Collection_point"
_DAILY_TRIP_ASSIGNMENT = "app.models.core_modules.daily_operations.daily_trip_assignment.DailyTripAssignment"
_DAILY_TRIP_LOG = "app.models.core_modules.daily_operations.daily_trip_log.DailyTripLog"
_DAILY_TRIP_COLLECTION_POINT = "app.models.core_modules.daily_operations.daily_trip_collection_point.DailyTripCollectionPoint"
_DAILY_TRIP_HOUSEHOLD_COLLECTION = "app.models.core_modules.daily_operations.daily_trip_household_collection.DailyTripHouseholdCollection"
_BIN_COLLECTION_EVENT = "app.models.core_modules.daily_operations.bin_collection_event.BinCollectionEvent"
_VEHICLE_BREAKDOWN = "app.models.core_modules.daily_operations.vehicle_breakdown.VehicleBreakdown"
_ROUTE_DETOUR_WAYPOINT = "app.models.core_modules.daily_operations.route_detour_waypoint.RouteDetourWaypoint"
_CUSTOMER_CREATION = "app.models.masters.customer_masters.customercreation.CustomerCreation"
_WASTE_COLLECTION = "app.models.core_modules.daily_operations.wastecollection.WasteCollection"
_COMPLAINT_TICKET = "app.models.core_modules.complaint_management.ticket.ComplaintTicket"
_COMPLAINT_ADDRESS_CHANGE = "app.models.core_modules.complaint_management.address_change.ComplaintAddressChangeRequest"
_COMPLAINT_EXTRA_DETAIL = "app.models.core_modules.complaint_management.transactions.ComplaintTicketExtraDetail"
_COMPLAINT_ATTACHMENT = "app.models.core_modules.complaint_management.transactions.ComplaintAttachment"
_COMPLAINT_STATUS_HISTORY = "app.models.core_modules.complaint_management.transactions.ComplaintStatusHistory"
_COMPLAINT_ASSIGNMENT_HISTORY = "app.models.core_modules.complaint_management.transactions.ComplaintAssignmentHistory"
_COMPLAINT_COMMENT = "app.models.core_modules.complaint_management.transactions.ComplaintComment"
_COMPLAINT_ROUTING_RULE = "app.models.core_modules.complaint_management.transactions.ComplaintRoutingRule"
_COMPLAINT_ESCALATION_HISTORY = "app.models.core_modules.complaint_management.transactions.ComplaintEscalationHistory"
_COMPLAINT_FEEDBACK = "app.models.core_modules.complaint_management.transactions.ComplaintFeedback"
_COMPLAINT_REOPEN_HISTORY = "app.models.core_modules.complaint_management.transactions.ComplaintReopenHistory"
_COMPLAINT_NOTIFICATION = "app.models.core_modules.complaint_management.transactions.ComplaintNotification"
_VEHICLE_CREATION = "app.models.masters.transport_masters.vehicleCreation.VehicleCreation"
_BINS = "app.models.masters.waste_masters.bins.Bins"
_STAFF_ACCESS_CONFIG = "app.models.superadmin.staff_management.staff_access_configuration.StaffAccessConfiguration"
_STAFF_ACCESS_CONFIG_PERM = "app.models.superadmin.staff_management.staff_access_configuration.StaffAccessConfigurationPermission"
_STAFF_PERSONAL_DETAILS = "app.models.superadmin.staff_management.staffcreation.StaffPersonalDetails"
_USER_TYPE = "app.models.superadmin.role_management.userType.UserType"
_STAFF_USER_TYPE = "app.models.superadmin.role_management.staffUserType.StaffUserType"
_CONTRACTOR_USER_TYPE = "app.models.superadmin.role_management.contractorUserType.ContractorUserType"
_PROJECT_STAFF_HIERARCHY = "app.models.superadmin.role_management.projectStaffHierarchy.ProjectStaffHierarchy"
_MAIN_SCREEN_TYPE = "app.models.superadmin.screen_management.mainscreentype.MainScreenType"
_MAIN_SCREEN = "app.models.superadmin.screen_management.mainscreen.MainScreen"
_USER_SCREEN = "app.models.superadmin.screen_management.userscreen.UserScreen"
_USER_SCREEN_ACTION = "app.models.superadmin.screen_management.userscreenaction.UserScreenAction"
_USER_SCREEN_COLUMN = "app.models.superadmin.screen_management.userscreencolumn.UserScreenColumn"
_COMPANY_USER_SCREEN_PERM = "app.models.superadmin.screen_management.companyuserscreenpermission.CompanyUserScreenPermission"
_COMPANY_USER_SCREEN_COL_PERM = "app.models.superadmin.screen_management.companyuserscreencolumnpermission.CompanyUserScreenColumnPermission"
_PROPERTY = "app.models.masters.waste_masters.property.Property"
_SUB_PROPERTY = "app.models.masters.waste_masters.subproperty.SubProperty"
_PLANT = "app.models.masters.plant.Plant"
_DISTRICT_LEADER_LOGIN = "app.models.masters.leader_management.district_leader_login.DistrictLeaderLogin"
_PANCHAYAT_LEADER_LOGIN = "app.models.masters.leader_management.panchayat_leader_login.PanchayatLeaderLogin"
_WASTE_TYPE = "app.models.waste_collection_bluetooth.waste_collection_bluetooth.WasteType"

# Company -> Projects, etc.
_register(_COMPANY, "projects", _PROJECT, "company_id")
_register(_COMPANY, "district_set", _DISTRICT, "company_id")
_register(_COMPANY, "plants", _PLANT, "company_id")
_register(_COMPANY, "departments", _DEPARTMENT, "company_id")
_register(_COMPANY, "designations", _DESIGNATION, "company_id")
_register(_COMPANY, "staff_office_details", _STAFF_CREATION, "company_id")
_register(_COMPANY, "staff_personal_details", _STAFF_PERSONAL_DETAILS, "company_id")
_register(_COMPANY, "staff_templates", _STAFF_TEMPLATE, "company_id")
_register(_COMPANY, "staffusertype_set", _STAFF_USER_TYPE, "company_id")
_register(_COMPANY, "contractorusertype_set", _CONTRACTOR_USER_TYPE, "company_id")
_register(_COMPANY, "usertype_set", _USER_TYPE, "company_id")
_register(_COMPANY, "wastetype_set", _WASTE_TYPE, "company_id")
_register(_COMPANY, "mainscreentype_set", _MAIN_SCREEN_TYPE, "company_id")
_register(_COMPANY, "mainscreen_set", _MAIN_SCREEN, "company_id")
_register(_COMPANY, "userscreen_set", _USER_SCREEN, "company_id")
_register(_COMPANY, "userscreenaction_set", _USER_SCREEN_ACTION, "company_id")
_register(_COMPANY, "userscreen_column_permissions", _COMPANY_USER_SCREEN_COL_PERM, "company_id")
_register(_COMPANY, "user_set", "app.models.superadmin_masters.auth_user.User", "company_id")
_register(_COMPANY, "maincategory_set", "app.models.core_modules.complaint_management.masters.ComplaintCategory", "company_id")
_register(_COMPANY, "complaint_set", _COMPLAINT_TICKET, "company_id")
_register(_COMPANY, "complaint_categories", "app.models.core_modules.complaint_management.masters.ComplaintCategory", "company_id")
_register(_COMPANY, "complaint_subcategories", "app.models.core_modules.complaint_management.masters.ComplaintSubcategory", "company_id")
_register(_COMPANY, "complaint_sla_rules", "app.models.core_modules.complaint_management.masters.ComplaintSlaRule", "company_id")
_register(_COMPANY, "staff_access_configurations", _STAFF_ACCESS_CONFIG, "company_id")
_register(_COMPANY, "customer_access_configurations", "app.models.masters.customer_masters.customer_access_configuration.CustomerAccessConfiguration", "company_id")
_register(_COMPANY, "property_set", _PROPERTY, "company_id")
_register(_COMPANY, "subproperty_set", _SUB_PROPERTY, "company_id")
_register(_COMPANY, "vehicle_creations", _VEHICLE_CREATION, "company_id")
_register(_COMPANY, "bin", _BINS, "company_id")

# Project -> district_set, etc.
_register(_PROJECT, "district_set", _DISTRICT, "project_id")
_register(_PROJECT, "plants", _PLANT, "project_id")
_register(_PROJECT, "departments", _DEPARTMENT, "project_id")
_register(_PROJECT, "designations", _DESIGNATION, "project_id")
_register(_PROJECT, "staff_office_details", _STAFF_CREATION, "project_id")
_register(_PROJECT, "staff_personal_details", _STAFF_PERSONAL_DETAILS, "project_id")
_register(_PROJECT, "staff_templates", _STAFF_TEMPLATE, "project_id")
_register(_PROJECT, "staffusertype_set", _STAFF_USER_TYPE, "project_id")
_register(_PROJECT, "contractorusertype_set", _CONTRACTOR_USER_TYPE, "project_id")
_register(_PROJECT, "usertype_set", _USER_TYPE, "project_id")
_register(_PROJECT, "wastetype_set", _WASTE_TYPE, "project_id")
_register(_PROJECT, "mainscreentype_set", _MAIN_SCREEN_TYPE, "project_id")
_register(_PROJECT, "mainscreen_set", _MAIN_SCREEN, "project_id")
_register(_PROJECT, "userscreen_set", _USER_SCREEN, "project_id")
_register(_PROJECT, "userscreenaction_set", _USER_SCREEN_ACTION, "project_id")
_register(_PROJECT, "userscreen_column_permissions", _COMPANY_USER_SCREEN_COL_PERM, "project_id")
_register(_PROJECT, "user_set", "app.models.superadmin_masters.auth_user.User", "project_id")
_register(_PROJECT, "maincategory_set", "app.models.core_modules.complaint_management.masters.ComplaintCategory", "project_id")
_register(_PROJECT, "complaint_set", _COMPLAINT_TICKET, "project_id")
_register(_PROJECT, "complaint_categories", "app.models.core_modules.complaint_management.masters.ComplaintCategory", "project_id")
_register(_PROJECT, "complaint_subcategories", "app.models.core_modules.complaint_management.masters.ComplaintSubcategory", "project_id")
_register(_PROJECT, "complaint_sla_rules", "app.models.core_modules.complaint_management.masters.ComplaintSlaRule", "project_id")
_register(_PROJECT, "property_set", _PROPERTY, "project_id")
_register(_PROJECT, "subproperty_set", _SUB_PROPERTY, "project_id")
_register(_PROJECT, "staff_hierarchy_levels", _PROJECT_STAFF_HIERARCHY, "project_id")

# State -> districts, customer_creation, complaint_routing_rules, etc.
_register(_STATE, "districts", _DISTRICT, "state_id")
_register(_STATE, "customer_creation", _CUSTOMER_CREATION, "state_id")
_register(_STATE, "complaint_routing_rules", _COMPLAINT_ROUTING_RULE, "state_id")
_register(_STATE, "complaint_tickets", _COMPLAINT_TICKET, "state_id")
_register(_STATE, "address_change_requests", _COMPLAINT_ADDRESS_CHANGE, "new_state_id")
_register(_STATE, "userscreenpermissions", _COMPANY_USER_SCREEN_PERM, "state_id")

# District -> cities, zone_set, panchayat, block_panchayat_unions, district_leader_logins, bin, cp, trip_plans, etc.
_register(_DISTRICT, "cities", _CITY, "district_id")
_register(_DISTRICT, "zone_set", _ZONE, "district_id")
_register(_DISTRICT, "panchayat", _PANCHAYAT, "district_id")
_register(_DISTRICT, "block_panchayat_unions", _BLOCK_PANCHAYAT_UNION, "district_id")
_register(_DISTRICT, "district_leader_logins", _DISTRICT_LEADER_LOGIN, "district_id")
_register(_DISTRICT, "bin", _BINS, "district_id")
_register(_DISTRICT, "cp", _COLLECTION_POINT, "district_id")
_register(_DISTRICT, "trip_plans", _TRIP_PLAN, "district_id")
_register(_DISTRICT, "address_change_requests", _COMPLAINT_ADDRESS_CHANGE, "new_district_id")
_register(_DISTRICT, "complaint_routing_rules", _COMPLAINT_ROUTING_RULE, "district_id")
_register(_DISTRICT, "complaint_tickets", _COMPLAINT_TICKET, "district_id")
_register(_DISTRICT, "customer_creation", _CUSTOMER_CREATION, "district_id")
_register(_DISTRICT, "users_district", "app.models.superadmin_masters.auth_user.User", "district_id")
_register(_DISTRICT, "userscreenpermissions", _COMPANY_USER_SCREEN_PERM, "district_id")
_register(_DISTRICT, "staff_district", _STAFF_CREATION, "district_id")

# City -> zone_set, panchayat, ward_set, bin, customer_creation, users_city, userscreenpermissions, staff_city
_register(_CITY, "zone_set", _ZONE, "city_id")
_register(_CITY, "panchayat", _PANCHAYAT, "city_id")
_register(_CITY, "ward_set", _WARD, "city_id")
_register(_CITY, "bin", _BINS, "city_id")
_register(_CITY, "customer_creation", _CUSTOMER_CREATION, "city_id")
_register(_CITY, "users_city", "app.models.superadmin_masters.auth_user.User", "city_id")
_register(_CITY, "userscreenpermissions", _COMPANY_USER_SCREEN_PERM, "city_id")
_register(_CITY, "staff_city", _STAFF_CREATION, "city_id")

# Zone -> wards, bin, trip_plans, customer_creation, users_zone, userscreenpermissions, staff_zone, complaint_routing_rules, complaint_tickets, address_change_requests
_register(_ZONE, "wards", _WARD, "zone_id")
_register(_ZONE, "bin", _BINS, "zone_id")
_register(_ZONE, "trip_plans", _TRIP_PLAN, "zone_id")
_register(_ZONE, "customer_creation", _CUSTOMER_CREATION, "zone_id")
_register(_ZONE, "users_zone", "app.models.superadmin_masters.auth_user.User", "zone_id")
_register(_ZONE, "userscreenpermissions", _COMPANY_USER_SCREEN_PERM, "zone_id")
_register(_ZONE, "staff_zone", _STAFF_CREATION, "zone_id")
_register(_ZONE, "complaint_routing_rules", _COMPLAINT_ROUTING_RULE, "zone_id")
_register(_ZONE, "complaint_tickets", _COMPLAINT_TICKET, "zone_id")
_register(_ZONE, "address_change_requests", _COMPLAINT_ADDRESS_CHANGE, "new_zone_id")

# Ward -> waste_collections, complaint_set, complaint_tickets, complaint_routing_rules, address_change_requests, bin, trip_plan_collection_points, daily_trip_collection_points, daily_trip_household_collections, bin_collection_events, customer_creation, users_ward, userscreenpermissions, staff_ward
_register(_WARD, "waste_collections", _WASTE_COLLECTION, "ward_id")
_register(_WARD, "complaint_set", _COMPLAINT_TICKET, "ward_id")
_register(_WARD, "complaint_tickets", _COMPLAINT_TICKET, "ward_id")
_register(_WARD, "complaint_routing_rules", _COMPLAINT_ROUTING_RULE, "ward_id")
_register(_WARD, "address_change_requests", _COMPLAINT_ADDRESS_CHANGE, "new_ward_id")
_register(_WARD, "bin", _BINS, "ward_id")
_register(_WARD, "trip_plan_collection_points", "app.models.core_modules.schedule_setup.trip_plan_collection_point.TripPlanCollectionPoint", "ward_id")
_register(_WARD, "daily_trip_collection_points", _DAILY_TRIP_COLLECTION_POINT, "ward_id")
_register(_WARD, "daily_trip_household_collections", _DAILY_TRIP_HOUSEHOLD_COLLECTION, "ward_id")
_register(_WARD, "bin_collection_events", _BIN_COLLECTION_EVENT, "ward_id")
_register(_WARD, "customer_creation", _CUSTOMER_CREATION, "ward_id")
_register(_WARD, "users_ward", "app.models.superadmin_masters.auth_user.User", "ward_id")
_register(_WARD, "userscreenpermissions", _COMPANY_USER_SCREEN_PERM, "ward_id")
_register(_WARD, "staff_ward", _STAFF_CREATION, "ward_id")

# Panchayat -> wards, leader_logins
_register(_PANCHAYAT, "wards", _WARD, "panchayat_id")
_register(_PANCHAYAT, "leader_logins", _PANCHAYAT_LEADER_LOGIN, "panchayat_id")

# BlockPanchayatUnion -> panchayats
_register(_BLOCK_PANCHAYAT_UNION, "panchayats", _PANCHAYAT, "block_id")

# StaffCreation -> personal_details, access_configuration
_register(_STAFF_CREATION, "personal_details", _STAFF_PERSONAL_DETAILS, "staff_unique_id")
_register(_STAFF_CREATION, "access_configuration", _STAFF_ACCESS_CONFIG, "staff_id")

# StaffAccessConfiguration -> granted_permissions
_register(_STAFF_ACCESS_CONFIG, "granted_permissions", _STAFF_ACCESS_CONFIG_PERM, "staff_access_configuration_id")

# TripPlan -> plan_collection_points, daily_trip_assignments
_register(_TRIP_PLAN, "plan_collection_points", "app.models.core_modules.schedule_setup.trip_plan_collection_point.TripPlanCollectionPoint", "trip_plan_id")
_register(_TRIP_PLAN, "daily_trip_assignments", _DAILY_TRIP_ASSIGNMENT, "trip_plan_id")

# DailyTripAssignment -> daily_trip_log, trip_collection_points, trip_household_collections, bin_collection_events, waste_collections, vehicle_breakdown
_register(_DAILY_TRIP_ASSIGNMENT, "daily_trip_log", _DAILY_TRIP_LOG, "trip_assignment_id")
_register(_DAILY_TRIP_ASSIGNMENT, "trip_collection_points", _DAILY_TRIP_COLLECTION_POINT, "trip_assignment_id")
_register(_DAILY_TRIP_ASSIGNMENT, "trip_household_collections", _DAILY_TRIP_HOUSEHOLD_COLLECTION, "trip_assignment_id")
_register(_DAILY_TRIP_ASSIGNMENT, "bin_collection_events", _BIN_COLLECTION_EVENT, "trip_assignment_id")
_register(_DAILY_TRIP_ASSIGNMENT, "waste_collections", _WASTE_COLLECTION, "trip_assignment_id")
_register(_DAILY_TRIP_ASSIGNMENT, "vehicle_breakdown", _VEHICLE_BREAKDOWN, "trip_assignment_id")
_register(_DAILY_TRIP_ASSIGNMENT, "route_detour_waypoints", _ROUTE_DETOUR_WAYPOINT, "trip_assignment_id")

# CollectionPoint -> bin, trip_plan_cps, daily_trip_logs, daily_trip_cps, bin_collection_events
_register(_COLLECTION_POINT, "bin", _BINS, "collection_point_id")
_register(_COLLECTION_POINT, "trip_plan_cps", "app.models.core_modules.schedule_setup.trip_plan_collection_point.TripPlanCollectionPoint", "collection_point_id")
_register(_COLLECTION_POINT, "daily_trip_logs", _DAILY_TRIP_LOG, "collection_point_id")
_register(_COLLECTION_POINT, "daily_trip_cps", _DAILY_TRIP_COLLECTION_POINT, "collection_point_id")
_register(_COLLECTION_POINT, "bin_collection_events", _BIN_COLLECTION_EVENT, "collection_point_id")

# CustomerCreation -> daily_trip_household_collections, waste_collections
_register(_CUSTOMER_CREATION, "daily_trip_household_collections", _DAILY_TRIP_HOUSEHOLD_COLLECTION, "customer_id")
_register(_CUSTOMER_CREATION, "waste_collections", _WASTE_COLLECTION, "customer_id")

# WasteCollection -> daily_trip_household_collections
_register(_WASTE_COLLECTION, "daily_trip_household_collections", _DAILY_TRIP_HOUSEHOLD_COLLECTION, "waste_collection_id")

# ComplaintTicket -> child_tickets, extra_details, attachments, feedback, address_change_request
_register(_COMPLAINT_TICKET, "child_tickets", _COMPLAINT_TICKET, "parent_ticket_id")
_register(_COMPLAINT_TICKET, "extra_details", _COMPLAINT_EXTRA_DETAIL, "ticket_id")
_register(_COMPLAINT_TICKET, "attachments", _COMPLAINT_ATTACHMENT, "ticket_id")
_register(_COMPLAINT_TICKET, "feedback", _COMPLAINT_FEEDBACK, "ticket_id")
_register(_COMPLAINT_TICKET, "address_change_request", _COMPLAINT_ADDRESS_CHANGE, "ticket_id")

# StaffTemplate -> trip_plans, daily_trip_assignments, daily_trip_logs
_register(_STAFF_TEMPLATE, "trip_plans", _TRIP_PLAN, "staff_template_id")
_register(_STAFF_TEMPLATE, "daily_trip_assignments", _DAILY_TRIP_ASSIGNMENT, "staff_template_id")
_register(_STAFF_TEMPLATE, "daily_trip_logs", _DAILY_TRIP_LOG, "staff_template_id")

# AlternativeStaffTemplate -> daily_trip_logs
_register(_ALT_STAFF_TEMPLATE, "daily_trip_logs", _DAILY_TRIP_LOG, "alt_staff_template_id")

# Bins -> trip_plan_cps, daily_trip_cps, bin_collection_events
_register(_BINS, "trip_plan_cps", "app.models.core_modules.schedule_setup.trip_plan_collection_point.TripPlanCollectionPoint", "bin_id")
_register(_BINS, "daily_trip_cps", _DAILY_TRIP_COLLECTION_POINT, "bin_id")
_register(_BINS, "bin_collection_events", _BIN_COLLECTION_EVENT, "bin_id")

# DailyTripCollectionPoint -> bin_collection_event
_register(_DAILY_TRIP_COLLECTION_POINT, "bin_collection_event", _BIN_COLLECTION_EVENT, "trip_collection_point_id")

# DailyTripLog -> (no children in CASCADE_SOFT_DELETE)

# VehicleBreakdown -> bin_collection_events
_register(_VEHICLE_BREAKDOWN, "bin_collection_events", _BIN_COLLECTION_EVENT, "vehicle_breakdown_id")

# MainScreenType -> mainscreens
_register(_MAIN_SCREEN_TYPE, "mainscreens", _MAIN_SCREEN, "mainscreentype_id")

# MainScreen -> userscreens, companyuserscreenpermissions
_register(_MAIN_SCREEN, "userscreens", _USER_SCREEN, "mainscreen_id")
_register(_MAIN_SCREEN, "companyuserscreenpermissions", _COMPANY_USER_SCREEN_PERM, "mainscreen_id")

# UserScreen -> userscreencolumns, userscreenactions, companyuserscreenpermissions
_register(_USER_SCREEN, "userscreencolumns", _USER_SCREEN_COLUMN, "userscreen_id")
_register(_USER_SCREEN, "userscreenactions", _USER_SCREEN_ACTION, "userscreen_id")
_register(_USER_SCREEN, "companyuserscreenpermissions", _COMPANY_USER_SCREEN_PERM, "userscreen_id")

# UserScreenAction -> companyuserscreenpermissions, companyuserscreencolumnpermissions, staff_access_configuration_permissions
_register(_USER_SCREEN_ACTION, "companyuserscreenpermissions", _COMPANY_USER_SCREEN_PERM, "userscreenaction_id")
_register(_USER_SCREEN_ACTION, "companyuserscreencolumnpermissions", _COMPANY_USER_SCREEN_COL_PERM, "userscreenaction_id")
_register(_USER_SCREEN_ACTION, "staff_access_configuration_permissions", _STAFF_ACCESS_CONFIG_PERM, "userscreenaction_id")

# UserScreenColumn -> companyuserscreencolumnpermissions
_register(_USER_SCREEN_COLUMN, "companyuserscreencolumnpermissions", _COMPANY_USER_SCREEN_COL_PERM, "column_id")

# CompanyUserScreenPermission -> companyuserscreencolumnpermissions
_register(_COMPANY_USER_SCREEN_PERM, "companyuserscreencolumnpermissions", _COMPANY_USER_SCREEN_COL_PERM, "userscreen_id")

# Department -> staff_members, designations
_register(_DEPARTMENT, "staff_members", _STAFF_CREATION, "department_id")
_register(_DEPARTMENT, "designations", _DESIGNATION, "department_id")

# Designation -> staff_members
_register(_DESIGNATION, "staff_members", _STAFF_CREATION, "designation_id")

# Country -> states, customer_creation
_register(_COUNTRY, "states", _STATE, "country_id")
_register(_COUNTRY, "customer_creation", _CUSTOMER_CREATION, "country_id")

# Continent -> countries, states, districts, cities
_register(_CONTINENT, "countries", _COUNTRY, "continent_id")
_register(_CONTINENT, "states", _STATE, "continent_id")
_register(_CONTINENT, "districts", _DISTRICT, "continent_id")
_register(_CONTINENT, "cities", _CITY, "continent_id")