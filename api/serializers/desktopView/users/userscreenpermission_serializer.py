from rest_framework import serializers
from django.db import models
from api.apps.userscreenpermission import UserScreenPermission
from api.apps.userType import UserType
from api.apps.userscreen import UserScreen


class UserScreenPermissionSerializer(serializers.ModelSerializer):
    userscreen_name = serializers.CharField(source="userscreen_id.userscreen_name", read_only=True)
    userscreenaction_name = serializers.CharField(source="userscreenaction_id.action_name", read_only=True)

    class Meta:
        model = UserScreenPermission
        fields = "__all__"


class ScreenActionSerializer(serializers.Serializer):
    userscreen_id = serializers.CharField()
    actions = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True
    )


class UserScreenPermissionMultiScreenSerializer(serializers.Serializer):
    usertype_id = serializers.CharField()
    staffusertype_id = serializers.CharField(required=False, allow_null=True)
    mainscreen_id = serializers.CharField()

    screens = ScreenActionSerializer(many=True)
    description = serializers.CharField(required=False, allow_blank=True)

    # ------------------------------------------------------------
    # VALIDATIONS
    # ------------------------------------------------------------
    def validate(self, data):
        ut_id = data["usertype_id"]

        try:
            ut = UserType.objects.get(unique_id=ut_id)
        except UserType.DoesNotExist:
            raise serializers.ValidationError({"usertype_id": "Invalid usertype"})

        # ROLE RESOLUTION
        ut_name = getattr(ut, "name", "").lower()

        if ut_name in ["customer", "client", "cust"]:
            data["resolved_staffusertype_id"] = None
        else:
            staff_ut = data.get("staffusertype_id")
            if not staff_ut:
                raise serializers.ValidationError({
                    "staffusertype_id": "staffusertype_id is required for staff usertype"
                })
            data["resolved_staffusertype_id"] = staff_ut

        # Validate screens belong to mainscreen
        ms_id = data["mainscreen_id"]

        for item in data["screens"]:
            userscreen_id = item["userscreen_id"]

            try:
                sc = UserScreen.objects.get(unique_id=userscreen_id, is_deleted=False)
            except UserScreen.DoesNotExist:
                raise serializers.ValidationError({"screens": f"Invalid userscreen {userscreen_id}"})

            if sc.mainscreen_id.unique_id != ms_id:
                raise serializers.ValidationError({
                    "screens": (
                        f"Screen {sc.userscreen_name} does not belong to "
                        f"Mainscreen {sc.mainscreen_id.mainscreen_name}"
                    )
                })

        return data

    # ------------------------------------------------------------
    # BULK CREATE / UPDATE / DELETE
    # ------------------------------------------------------------
    def create(self, validated_data):
        ut = validated_data["usertype_id"]
        stu = validated_data["resolved_staffusertype_id"]
        ms = validated_data["mainscreen_id"]
        screens = validated_data["screens"]
        desc = validated_data.get("description", "")

        created = []
        updated = []
        deleted = []

        for scr in screens:
            userscreen_id = scr["userscreen_id"]
            incoming_actions = scr["actions"]

            qs = UserScreenPermission.objects.filter(
                usertype_id_id=ut,
                staffusertype_id_id=stu,
                mainscreen_id_id=ms,
                userscreen_id_id=userscreen_id,
                is_deleted=False
            )

            existing = {obj.userscreenaction_id_id: obj for obj in qs}

            max_order = qs.aggregate(models.Max("order_no")).get("order_no__max") or 0
            order_no = max_order + 1

            # CREATE + UPDATE
            for action_id in incoming_actions:
                if action_id in existing:
                    obj = existing[action_id]
                    obj.description = desc
                    obj.is_active = True
                    obj.is_deleted = False
                    obj.save()
                    updated.append(obj)
                else:
                    obj = UserScreenPermission.objects.create(
                        usertype_id_id=ut,
                        staffusertype_id_id=stu,
                        mainscreen_id_id=ms,
                        userscreen_id_id=userscreen_id,
                        userscreenaction_id_id=action_id,
                        description=desc,
                        order_no=order_no
                    )
                    created.append(obj)
                    order_no += 1

            # DELETE missing actions
            for action_id, obj in existing.items():
                if action_id not in incoming_actions:
                    obj.is_deleted = True
                    obj.is_active = False
                    obj.save()
                    deleted.append(obj)

        return {
            "created": created,
            "updated": updated,
            "deleted": deleted
        }
