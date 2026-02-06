from rest_framework import serializers
from app.models.screen_managements.companyuserscreenpermission import CompanyUserScreenPermission
from app.models.role_assigns.userType import UserType
from app.models.screen_managements.userscreen import UserScreen
from app.models.superadmin_masters.company import Company


# =============================================================
# SINGLE PERMISSION SERIALIZER (GET / LIST)
# =============================================================
class CompanyUserScreenPermissionSerializer(serializers.ModelSerializer):
    userscreen_name = serializers.CharField(
        source="userscreen_id.userscreen_name", read_only=True
    )
    userscreenaction_name = serializers.CharField(
        source="userscreenaction_id.action_name", read_only=True
    )
    usertype_name = serializers.CharField(
        source="usertype_id.name", read_only=True
    )
    staffusertype_name = serializers.CharField(
        source="staffusertype_id.name", read_only=True
    )
    mainscreen_name = serializers.CharField(
        source="mainscreen_id.mainscreen_name", read_only=True
    )

    class Meta:
        model = CompanyUserScreenPermission
        fields = "__all__"


# =============================================================
# Nested Screen → Action Serializer
# =============================================================
class ScreenActionSerializer(serializers.Serializer):
    userscreen_id = serializers.CharField()
    actions = serializers.ListField(
        child=serializers.CharField(), allow_empty=True
    )


# =============================================================
# MULTI-SCREEN BULK CREATE / UPDATE / REVIVE / SOFT DELETE
# =============================================================
class CompanyUserScreenPermissionMultiScreenSerializer(serializers.Serializer):
    company_id = serializers.CharField()
    usertype_id = serializers.CharField()
    staffusertype_id = serializers.CharField(required=False, allow_null=True)
    mainscreen_id = serializers.CharField()
    screens = ScreenActionSerializer(many=True)
    description = serializers.CharField(required=False, allow_blank=True)

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------
    def validate(self, data):
        # Company
        try:
            company = Company.objects.get(unique_id=data["company_id"])
        except Company.DoesNotExist:
            raise serializers.ValidationError({"company_id": "Invalid company"})

        data["resolved_company_id"] = company.unique_id

        # UserType
        try:
            ut = UserType.objects.get(unique_id=data["usertype_id"])
        except UserType.DoesNotExist:
            raise serializers.ValidationError({"usertype_id": "Invalid usertype"})

        ut_name = ut.name.lower()

        # Staff / Customer logic
        if ut_name in ["customer", "client", "cust"]:
            data["resolved_staffusertype_id"] = None
        else:
            if not data.get("staffusertype_id"):
                raise serializers.ValidationError({
                    "staffusertype_id": "Required for staff roles"
                })
            data["resolved_staffusertype_id"] = data["staffusertype_id"]

        # Screen → Mainscreen validation
        for scr in data["screens"]:
            try:
                screen = UserScreen.objects.get(
                    unique_id=scr["userscreen_id"], is_deleted=False
                )
            except UserScreen.DoesNotExist:
                raise serializers.ValidationError({
                    "screens": f"Invalid screen {scr['userscreen_id']}"
                })

            if screen.mainscreen_id.unique_id != data["mainscreen_id"]:
                raise serializers.ValidationError({
                    "screens": f"{screen.userscreen_name} does not belong to this mainscreen"
                })

        return data

    # ---------------------------------------------------------
    # BULK SYNC
    # ---------------------------------------------------------
    def create(self, validated_data):
        company_id = validated_data["resolved_company_id"]
        ut = validated_data["usertype_id"]
        st = validated_data["resolved_staffusertype_id"]
        ms = validated_data["mainscreen_id"]
        screens = validated_data["screens"]
        desc = validated_data.get("description", "")

        created, updated, deleted = [], [], []

        for scr in screens:
            scr_id = scr["userscreen_id"]
            incoming_actions = scr["actions"]

            qs = CompanyUserScreenPermission.objects.filter(
                company_id_id=company_id,
                usertype_id_id=ut,
                staffusertype_id_id=st,
                mainscreen_id_id=ms,
                userscreen_id_id=scr_id,
            )

            existing = {o.userscreenaction_id_id: o for o in qs}
            order_no = 1

            # CREATE / UPDATE / REVIVE
            for act_id in incoming_actions:
                if act_id in existing:
                    obj = existing[act_id]
                    obj.is_deleted = False
                    obj.is_active = True
                    obj.order_no = order_no
                    obj.description = desc
                    obj.save()
                    updated.append(obj)
                else:
                    obj = CompanyUserScreenPermission.objects.create(
                        company_id_id=company_id,
                        usertype_id_id=ut,
                        staffusertype_id_id=st,
                        mainscreen_id_id=ms,
                        userscreen_id_id=scr_id,
                        userscreenaction_id_id=act_id,
                        description=desc,
                        order_no=order_no,
                    )
                    created.append(obj)
                order_no += 1

            # SOFT DELETE missing actions
            for act_id, obj in existing.items():
                if act_id not in incoming_actions:
                    obj.is_deleted = True
                    obj.is_active = False
                    obj.save()
                    deleted.append(obj)

        return {
            "created": created,
            "updated": updated,
            "deleted": deleted,
        }
