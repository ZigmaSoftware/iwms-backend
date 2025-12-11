from rest_framework import serializers
from django.db import models

from api.apps.userscreenpermission import UserScreenPermission
from api.apps.userType import UserType
from api.apps.userscreen import UserScreen


# =============================================================
# SINGLE PERMISSION SERIALIZER (Used for GET, LIST)
# =============================================================
class UserScreenPermissionSerializer(serializers.ModelSerializer):
    userscreen_name = serializers.CharField(source="userscreen_id.userscreen_name", read_only=True)
    userscreenaction_name = serializers.CharField(source="userscreenaction_id.action_name", read_only=True)

    usertype_name = serializers.CharField(source="usertype_id.name", read_only=True)
    staffusertype_name = serializers.CharField(source="staffusertype_id.name", read_only=True)

    mainscreen_name = serializers.CharField(source="mainscreen_id.mainscreen_name", read_only=True)

    class Meta:
        model = UserScreenPermission
        fields = "__all__"


# =============================================================
# Nested Screen → Action Serializer
# =============================================================
class ScreenActionSerializer(serializers.Serializer):
    userscreen_id = serializers.CharField()
    actions = serializers.ListField(child=serializers.CharField(), allow_empty=True)


# =============================================================
# MULTI-SCREEN BULK CREATE / UPDATE / REVIVE / SOFT DELETE
# =============================================================
class UserScreenPermissionMultiScreenSerializer(serializers.Serializer):
    usertype_id = serializers.CharField()
    staffusertype_id = serializers.CharField(required=False, allow_null=True)
    mainscreen_id = serializers.CharField()

    screens = ScreenActionSerializer(many=True)
    description = serializers.CharField(required=False, allow_blank=True)

    # ----------------------------
    # VALIDATION
    # ----------------------------
    def validate(self, data):
        ut_id = data["usertype_id"]

        # Validate usertype
        try:
            ut = UserType.objects.get(unique_id=ut_id)
        except UserType.DoesNotExist:
            raise serializers.ValidationError({"usertype_id": "Invalid usertype"})

        ut_name = getattr(ut, "name", "").lower()

        # Customer type: staffusertype must be null
        if ut_name in ["customer", "client", "cust"]:
            data["resolved_staffusertype_id"] = None
        else:
            st = data.get("staffusertype_id")
            if not st:
                raise serializers.ValidationError({
                    "staffusertype_id": "staffusertype_id is required for staff roles"
                })
            data["resolved_staffusertype_id"] = st

        ms = data["mainscreen_id"]

        # Validate screen belongs to mainscreen
        for scr in data["screens"]:
            try:
                sc = UserScreen.objects.get(unique_id=scr["userscreen_id"], is_deleted=False)
            except UserScreen.DoesNotExist:
                raise serializers.ValidationError({"screens": f"Invalid screen {scr['userscreen_id']}"})

            if sc.mainscreen_id.unique_id != ms:
                raise serializers.ValidationError({
                    "screens": f"{sc.userscreen_name} does not belong to {sc.mainscreen_id.mainscreen_name}"
                })

        return data

    # ----------------------------
    # BULK SYNC (Create, Update, Revive, Delete)
    # ----------------------------
    def create(self, validated_data):
        ut = validated_data["usertype_id"]
        st = validated_data["resolved_staffusertype_id"]
        ms = validated_data["mainscreen_id"]
        screens = validated_data["screens"]
        desc = validated_data.get("description", "")

        created, updated, deleted = [], [], []

        for scr in screens:
            scr_id = scr["userscreen_id"]
            incoming_actions = scr["actions"]

            # Fetch ALL existing records (including soft deleted)
            qs = UserScreenPermission.objects.filter(
                usertype_id_id=ut,
                staffusertype_id_id=st,
                mainscreen_id_id=ms,
                userscreen_id_id=scr_id
            )

            existing = {obj.userscreenaction_id_id: obj for obj in qs}

            order_no = 1

            # CREATE + REVIVE + UPDATE
            for act_id in incoming_actions:

                if act_id in existing:
                    obj = existing[act_id]

                    # revive soft-deleted
                    obj.is_deleted = False
                    obj.is_active = True

                    obj.description = desc
                    obj.order_no = order_no
                    obj.save()

                    updated.append(obj)
                else:
                    # create fresh
                    obj = UserScreenPermission.objects.create(
                        usertype_id_id=ut,
                        staffusertype_id_id=st,
                        mainscreen_id_id=ms,
                        userscreen_id_id=scr_id,
                        userscreenaction_id_id=act_id,
                        description=desc,
                        order_no=order_no
                    )
                    created.append(obj)

                order_no += 1

            # DELETE actions missing from incoming
            for act_id, obj in existing.items():
                if act_id not in incoming_actions:
                    obj.is_deleted = True
                    obj.is_active = False
                    obj.save()
                    deleted.append(obj)

        return {
            "created": created,
            "updated": updated,
            "deleted": deleted
        }
