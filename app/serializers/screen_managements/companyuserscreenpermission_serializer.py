# from rest_framework import serializers

# from app.models.screen_managements.companyuserscreenpermission import CompanyUserScreenPermission
# from app.models.role_assigns.userType import UserType
# from app.models.screen_managements.userscreen import UserScreen
# from app.models.screen_managements.userscreenaction import UserScreenAction
# from app.models.superadmin_masters.company import Company
# from app.models.screen_managements.mainscreen import MainScreen
# from app.models.role_assigns.staffUserType import StaffUserType


# # ---------------------------------------------------------
# # BASIC SERIALIZER
# # ---------------------------------------------------------

# class CompanyUserScreenPermissionSerializer(serializers.ModelSerializer):
#     userscreen_name = serializers.CharField(source="userscreen_id.userscreen_name", read_only=True)
#     userscreenaction_name = serializers.CharField(source="userscreenaction_id.action_name", read_only=True)
#     usertype_name = serializers.CharField(source="usertype_id.name", read_only=True)
#     staffusertype_name = serializers.CharField(source="staffusertype_id.name", read_only=True)
#     mainscreen_name = serializers.CharField(source="mainscreen_id.mainscreen_name", read_only=True)
#     company_name = serializers.CharField(source="company_id.name", read_only=True)

#     class Meta:
#         model = CompanyUserScreenPermission
#         fields = "__all__"


# # ---------------------------------------------------------
# # INPUT STRUCTURE
# # ---------------------------------------------------------

# class ScreenActionSerializer(serializers.Serializer):
#     userscreen_id = serializers.CharField()
#     actions = serializers.ListField(child=serializers.CharField(), allow_empty=True)


# # ---------------------------------------------------------
# # MAIN BULK SERIALIZER (FIXED)
# # ---------------------------------------------------------

# class CompanyUserScreenPermissionMultiScreenSerializer(serializers.Serializer):
#     company_id = serializers.CharField()
#     usertype_id = serializers.CharField()
#     staffusertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
#     mainscreen_id = serializers.CharField()
#     screens = ScreenActionSerializer(many=True)
#     description = serializers.CharField(required=False, allow_blank=True)

#     # ---------------------------------------------------------
#     # VALIDATION
#     # ---------------------------------------------------------

#     def validate(self, data):
#         # 🔥 Trim all inputs (VERY IMPORTANT)
#         data["company_id"] = data["company_id"].strip()
#         data["usertype_id"] = data["usertype_id"].strip()
#         data["mainscreen_id"] = data["mainscreen_id"].strip()

#         if data.get("staffusertype_id"):
#             data["staffusertype_id"] = data["staffusertype_id"].strip()

#         # Company
#         try:
#             company = Company.objects.get(unique_id=data["company_id"], is_deleted=False)
#         except Company.DoesNotExist:
#             raise serializers.ValidationError({"company_id": "Invalid company"})

#         # Usertype
#         try:
#             usertype = UserType.objects.get(unique_id=data["usertype_id"], is_deleted=False)
#         except UserType.DoesNotExist:
#             raise serializers.ValidationError({"usertype_id": "Invalid usertype"})

#         # Mainscreen
#         try:
#             mainscreen = MainScreen.objects.get(unique_id=data["mainscreen_id"], is_deleted=False)
#         except MainScreen.DoesNotExist:
#             raise serializers.ValidationError({"mainscreen_id": "Invalid mainscreen"})

#         # Staff logic
#         ut_name = (usertype.name or "").lower()

#         if ut_name in {"customer", "client", "cust"}:
#             resolved_staffusertype_id = None
#         else:
#             if not data.get("staffusertype_id"):
#                 raise serializers.ValidationError({"staffusertype_id": "Required for staff roles"})

#             try:
#                 StaffUserType.objects.get(unique_id=data["staffusertype_id"], is_deleted=False)
#             except StaffUserType.DoesNotExist:
#                 raise serializers.ValidationError({"staffusertype_id": "Invalid staffusertype"})

#             resolved_staffusertype_id = data["staffusertype_id"]

#         # Validate screens
#         if not data.get("screens"):
#             raise serializers.ValidationError({"screens": "At least one screen required"})

#         # Validate actions
#         all_action_ids = set()
#         for scr in data["screens"]:
#             for aid in scr.get("actions", []):
#                 all_action_ids.add(aid)

#         if all_action_ids:
#             valid_ids = set(
#                 UserScreenAction.objects.filter(unique_id__in=all_action_ids, is_deleted=False)
#                 .values_list("unique_id", flat=True)
#             )

#             invalid = all_action_ids - valid_ids
#             if invalid:
#                 raise serializers.ValidationError({"screens": f"Invalid actions: {', '.join(invalid)}"})

#         # Attach resolved values
#         data["resolved_company_id"] = company.unique_id
#         data["resolved_usertype_id"] = usertype.unique_id
#         data["resolved_staffusertype_id"] = resolved_staffusertype_id
#         data["resolved_mainscreen_id"] = mainscreen.unique_id

#         return data

#     # ---------------------------------------------------------
#     # CORE LOGIC (NO DUPLICATES EVER)
#     # ---------------------------------------------------------

#     def create(self, validated_data):
#         company_id = validated_data["resolved_company_id"]
#         usertype_id = validated_data["resolved_usertype_id"]
#         staffusertype_id = validated_data["resolved_staffusertype_id"]
#         mainscreen_id = validated_data["resolved_mainscreen_id"]
#         screens = validated_data["screens"]
#         desc = (validated_data.get("description") or "").strip()
#         update_only = bool(self.context.get("update_only", False))

#         created, updated, deleted = [], [], []
#         missing_keys = []

#         # 🔥 Load existing once
#         existing_qs = CompanyUserScreenPermission.objects.filter(
#             company_id_id=company_id,
#             usertype_id_id=usertype_id,
#             staffusertype_id_id=staffusertype_id,
#             mainscreen_id_id=mainscreen_id,
#         )

#         existing_lookup = {
#             (obj.userscreen_id_id, obj.userscreenaction_id_id): obj
#             for obj in existing_qs
#         }

#         incoming_keys = set()

#         # 🔁 Process incoming
#         for scr in screens:
#             scr_id = scr["userscreen_id"]
#             order_no = 1

#             for act_id in scr["actions"]:
#                 key = (scr_id, act_id)
#                 incoming_keys.add(key)

#                 obj = existing_lookup.get(key)

#                 if obj:
#                     # UPDATE
#                     if obj.is_deleted or not obj.is_active or obj.order_no != order_no or obj.description != desc:
#                         obj.is_deleted = False
#                         obj.is_active = True
#                         obj.order_no = order_no
#                         obj.description = desc
#                         obj.save(update_fields=[
#                             "is_deleted",
#                             "is_active",
#                             "order_no",
#                             "description",
#                             "updated_at",
#                         ])
#                         updated.append(obj)
#                 else:
#                     if update_only:
#                         missing_keys.append(key)
#                         order_no += 1
#                         continue
#                     # CREATE
#                     obj = CompanyUserScreenPermission.objects.create(
#                         company_id_id=company_id,
#                         usertype_id_id=usertype_id,
#                         staffusertype_id_id=staffusertype_id,
#                         mainscreen_id_id=mainscreen_id,
#                         userscreen_id_id=scr_id,
#                         userscreenaction_id_id=act_id,
#                         description=desc,
#                         order_no=order_no,
#                         is_deleted=False,
#                         is_active=True,
#                     )
#                     created.append(obj)

#                 order_no += 1

#         # Update-only guard
#         if update_only and missing_keys:
#             sample = ", ".join(f"{screen}:{action}" for screen, action in missing_keys[:5])
#             raise serializers.ValidationError(
#                 {
#                     "screens": (
#                         "Update mode cannot create new permissions. "
#                         f"New selections found: {sample}"
#                     )
#                 }
#             )

#         # Soft delete missing
#         for key, obj in existing_lookup.items():
#             if key not in incoming_keys:
#                 if not obj.is_deleted:
#                     obj.is_deleted = True
#                     obj.is_active = False
#                     obj.save(update_fields=["is_deleted", "is_active", "updated_at"])
#                     deleted.append(obj)

#         return {"created": created, "updated": updated, "deleted": deleted}



from rest_framework import serializers

from app.models.screen_managements.companyuserscreenpermission import CompanyUserScreenPermission
from app.models.screen_managements.companyuserscreencolumnpermission import CompanyUserScreenColumnPermission
from app.models.role_assigns.userType import UserType
from app.models.screen_managements.userscreen import UserScreen
from app.models.screen_managements.userscreenaction import UserScreenAction
from app.models.screen_managements.userscreencolumn import UserScreenColumn
from app.models.superadmin_masters.company import Company
from app.models.screen_managements.mainscreen import MainScreen
from app.models.role_assigns.staffUserType import StaffUserType


# ---------------------------------------------------------
# BASIC SERIALIZER
# ---------------------------------------------------------

class CompanyUserScreenPermissionSerializer(serializers.ModelSerializer):
    userscreen_name = serializers.CharField(source="userscreen_id.userscreen_name", read_only=True)
    userscreenaction_name = serializers.CharField(source="userscreenaction_id.action_name", read_only=True)
    usertype_name = serializers.CharField(source="usertype_id.name", read_only=True)
    staffusertype_name = serializers.CharField(source="staffusertype_id.name", read_only=True)
    mainscreen_name = serializers.CharField(source="mainscreen_id.mainscreen_name", read_only=True)
    company_name = serializers.CharField(source="company_id.name", read_only=True)

    class Meta:
        model = CompanyUserScreenPermission
        fields = "__all__"


# ---------------------------------------------------------
# INPUT STRUCTURE
# ---------------------------------------------------------

class ScreenActionSerializer(serializers.Serializer):
    userscreen_id = serializers.CharField()
    actionIds = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    columnIds = serializers.ListField(child=serializers.CharField(), allow_empty=True, required=False)


# ---------------------------------------------------------
# MAIN BULK SERIALIZER (FIXED)
# ---------------------------------------------------------

class CompanyUserScreenPermissionMultiScreenSerializer(serializers.Serializer):
    company_id = serializers.CharField()
    usertype_id = serializers.CharField()
    staffusertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    mainscreen_id = serializers.CharField()
    screens = ScreenActionSerializer(many=True)
    description = serializers.CharField(required=False, allow_blank=True)

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    def validate(self, data):
        data["company_id"] = data["company_id"].strip()
        data["usertype_id"] = data["usertype_id"].strip()
        data["mainscreen_id"] = data["mainscreen_id"].strip()

        if data.get("staffusertype_id"):
            data["staffusertype_id"] = data["staffusertype_id"].strip()

        # Company
        try:
            company = Company.objects.get(unique_id=data["company_id"], is_deleted=False)
        except Company.DoesNotExist:
            raise serializers.ValidationError({"company_id": "Invalid company"})

        # Usertype
        try:
            usertype = UserType.objects.get(unique_id=data["usertype_id"], is_deleted=False)
        except UserType.DoesNotExist:
            raise serializers.ValidationError({"usertype_id": "Invalid usertype"})

        # Mainscreen
        try:
            mainscreen = MainScreen.objects.get(unique_id=data["mainscreen_id"], is_deleted=False)
        except MainScreen.DoesNotExist:
            raise serializers.ValidationError({"mainscreen_id": "Invalid mainscreen"})

        # Staff logic
        ut_name = (usertype.name or "").lower()

        if ut_name in {"customer", "client", "cust"}:
            resolved_staffusertype_id = None
        else:
            if not data.get("staffusertype_id"):
                raise serializers.ValidationError({"staffusertype_id": "Required for staff roles"})

            try:
                StaffUserType.objects.get(unique_id=data["staffusertype_id"], is_deleted=False)
            except StaffUserType.DoesNotExist:
                raise serializers.ValidationError({"staffusertype_id": "Invalid staffusertype"})

            resolved_staffusertype_id = data["staffusertype_id"]

        # Validate screens
        if not data.get("screens"):
            raise serializers.ValidationError({"screens": "At least one screen required"})

        # Validate actions
        all_action_ids = set()
        for scr in data["screens"]:
            for aid in scr.get("actionIds", []):
                all_action_ids.add(aid)

        if all_action_ids:
            valid_ids = set(
                UserScreenAction.objects.filter(unique_id__in=all_action_ids, is_deleted=False)
                .values_list("unique_id", flat=True)
            )

            invalid = all_action_ids - valid_ids
            if invalid:
                raise serializers.ValidationError({"screens": f"Invalid actions: {', '.join(invalid)}"})

        # Validate columns
        all_column_ids = set()
        for scr in data["screens"]:
            for cid in scr.get("columnIds", []):
                all_column_ids.add(cid)

        if all_column_ids:
            valid_ids = set(
                UserScreenColumn.objects.filter(unique_id__in=all_column_ids, is_deleted=False)
                .values_list("unique_id", flat=True)
            )

            invalid = all_column_ids - valid_ids
            if invalid:
                raise serializers.ValidationError({"screens": f"Invalid columns: {', '.join(invalid)}"})

        # Attach resolved values
        data["resolved_company_id"] = company.unique_id
        data["resolved_usertype_id"] = usertype.unique_id
        data["resolved_staffusertype_id"] = resolved_staffusertype_id
        data["resolved_mainscreen_id"] = mainscreen.unique_id

        return data

    # ---------------------------------------------------------
    # CORE LOGIC (EXTENDED FOR COLUMN PERMISSIONS)
    # ---------------------------------------------------------

    def create(self, validated_data):
        company_id = validated_data["resolved_company_id"]
        usertype_id = validated_data["resolved_usertype_id"]
        staffusertype_id = validated_data["resolved_staffusertype_id"]
        mainscreen_id = validated_data["resolved_mainscreen_id"]
        screens = validated_data["screens"]
        desc = (validated_data.get("description") or "").strip()
        update_only = bool(self.context.get("update_only", False))

        created, updated, deleted = [], [], []
        created_columns, updated_columns, deleted_columns = [], [], []
        missing_keys = []

        existing_qs = CompanyUserScreenPermission.objects.filter(
            company_id_id=company_id,
            usertype_id_id=usertype_id,
            staffusertype_id_id=staffusertype_id,
            mainscreen_id_id=mainscreen_id,
        )

        existing_lookup = {
            (obj.userscreen_id_id, obj.userscreenaction_id_id): obj
            for obj in existing_qs
        }

        incoming_keys = set()

        for scr in screens:
            scr_id = scr["userscreen_id"]
            action_ids = scr.get("actionIds", [])
            column_ids = scr.get("columnIds", [])

            order_no = 1

            # Process actions
            for act_id in action_ids:
                key = (scr_id, act_id)
                incoming_keys.add(key)

                obj = existing_lookup.get(key)

                if obj:
                    # UPDATE existing action permission
                    if obj.is_deleted or not obj.is_active or obj.order_no != order_no or obj.description != desc:
                        obj.is_deleted = False
                        obj.is_active = True
                        obj.order_no = order_no
                        obj.description = desc
                        obj.save(update_fields=[
                            "is_deleted",
                            "is_active",
                            "order_no",
                            "description",
                            "updated_at",
                        ])
                        updated.append(obj)
                else:
                    # CREATE new action permission
                    obj = CompanyUserScreenPermission(
                        company_id_id=company_id,
                        usertype_id_id=usertype_id,
                        staffusertype_id_id=staffusertype_id,
                        mainscreen_id_id=mainscreen_id,
                        userscreen_id_id=scr_id,
                        userscreenaction_id_id=act_id,
                        description=desc,
                        order_no=order_no,
                        is_deleted=False,
                        is_active=True,
                    )
                    obj.save()
                    created.append(obj)

                # Process column permissions for this action
                if column_ids:
                    self._process_column_permissions(
                        obj, column_ids, desc,
                        created_columns, updated_columns, deleted_columns
                    )

                order_no += 1

        # Soft delete action permissions that are no longer needed
        for key, obj in existing_lookup.items():
            if key not in incoming_keys:
                if not obj.is_deleted:
                    obj.is_deleted = True
                    obj.is_active = False
                    obj.save(update_fields=["is_deleted", "is_active", "updated_at"])
                    deleted.append(obj)

                    # Also soft delete associated column permissions
                    CompanyUserScreenColumnPermission.objects.filter(
                        companyuserscreenpermission_id=obj.unique_id,
                        is_deleted=False
                    ).update(
                        is_deleted=True,
                        is_active=False,
                        updated_at=obj.updated_at
                    )

        return {
            "created": created,
            "updated": updated,
            "deleted": deleted,
            "created_columns": created_columns,
            "updated_columns": updated_columns,
            "deleted_columns": deleted_columns
        }

    def _process_column_permissions(self, action_permission, column_ids, desc,
                                   created_columns, updated_columns, deleted_columns):
        """
        Process column permissions for a given action permission.
        """
        # Get existing column permissions for this action
        existing_column_perms = CompanyUserScreenColumnPermission.objects.filter(
            companyuserscreenpermission_id=action_permission.unique_id,
            is_deleted=False
        )

        existing_lookup = {
            obj.userscreencolumn_id_id: obj
            for obj in existing_column_perms
        }

        incoming_column_keys = set(column_ids)
        order_no = 1

        for col_id in column_ids:
            obj = existing_lookup.get(col_id)

            if obj:
                # UPDATE existing column permission
                if obj.is_deleted or not obj.is_active or obj.order_no != order_no:
                    obj.is_deleted = False
                    obj.is_active = True
                    obj.order_no = order_no
                    obj.description = desc
                    obj.save(update_fields=[
                        "is_deleted", "is_active", "order_no", "description", "updated_at"
                    ])
                    updated_columns.append(obj)
            else:
                # CREATE new column permission
                obj = CompanyUserScreenColumnPermission(
                    companyuserscreenpermission_id=action_permission.unique_id,
                    userscreencolumn_id_id=col_id,
                    can_view=True,  # Default permissions
                    can_edit=False,
                    can_filter=True,
                    can_search=True,
                    can_sort=True,
                    description=desc,
                    order_no=order_no,
                    is_deleted=False,
                    is_active=True,
                )
                obj.save()
                created_columns.append(obj)

            order_no += 1

        # Soft delete column permissions that are no longer in the list
        for col_key, obj in existing_lookup.items():
            if col_key not in incoming_column_keys:
                if not obj.is_deleted:
                    obj.is_deleted = True
                    obj.is_active = False
                    obj.save(update_fields=["is_deleted", "is_active", "updated_at"])
                    deleted_columns.append(obj)