from rest_framework import serializers
from api.apps.userscreenpermission import UserScreenPermission
from api.apps.userType import UserType
from api.apps.userscreen import UserScreen


class UserScreenPermissionSerializer(serializers.ModelSerializer):
    userscreen_name = serializers.CharField(source="userscreen_id.userscreen_name", read_only=True)
    userscreenaction_name = serializers.CharField(source="userscreenaction_id.action_name", read_only=True)

    class Meta:
        model = UserScreenPermission
        fields = "__all__"


class UserScreenPermissionBulkSerializer(serializers.Serializer):
    usertype_id = serializers.CharField()
    staffusertype_id = serializers.CharField(required=False, allow_null=True)
    mainscreen_id = serializers.CharField()
    userscreen_id = serializers.CharField()

    userscreenaction_ids = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False
    )

    description = serializers.CharField(required=False, allow_blank=True)

    # ------------------------------------------------------------
    # VALIDATIONS
    # ------------------------------------------------------------
    def validate(self, data):
        usertype_id = data["usertype_id"]
        staffusertype_id = data.get("staffusertype_id")

        # -------------------------------
        # VALIDATE USER TYPE
        # -------------------------------
        try:
            ut = UserType.objects.get(unique_id=usertype_id)
        except UserType.DoesNotExist:
            raise serializers.ValidationError({"usertype_id": "Invalid usertype"})

        # Detect customer type by common name fields
        ut_name = getattr(ut, "name", None) or getattr(ut, "user_type", None)

        if ut_name and ut_name.lower() in ["customer", "client", "cust"]:
            data["staffusertype_id"] = None

        # -------------------------------
        # VALIDATE SCREEN BELONGS TO MAINSCREEN
        # -------------------------------
        try:
            screen = UserScreen.objects.get(unique_id=data["userscreen_id"], is_deleted=False)
        except UserScreen.DoesNotExist:
            raise serializers.ValidationError({"userscreen_id": "Invalid userscreen"})

        if screen.mainscreen_id.unique_id != data["mainscreen_id"]:
            raise serializers.ValidationError({
                "userscreen_id": (
                    f"Userscreen '{screen.userscreen_name}' does not belong to "
                    f"Mainscreen '{screen.mainscreen_id.mainscreen_name}'."
                )
            })

        return data

    # ------------------------------------------------------------
    # CREATE LOGIC
    # ------------------------------------------------------------
    def create(self, validated_data):
        usertype_id = validated_data["usertype_id"]
        staffusertype_id = validated_data.get("staffusertype_id")
        mainscreen_id = validated_data["mainscreen_id"]
        userscreen_id = validated_data["userscreen_id"]
        actions = validated_data["userscreenaction_ids"]
        description = validated_data.get("description", "")

        created_objs = []
        skipped = []

        # Determine last order_no FOR THE ROLE
        last = UserScreenPermission.objects.filter(
            usertype_id_id=usertype_id,
            staffusertype_id_id=staffusertype_id,
            mainscreen_id_id=mainscreen_id
        ).order_by("-order_no").first()

        order_no = (last.order_no + 1) if last else 1

        # ------------------------------------------------------------
        # CREATE FOR EACH ACTION
        # ------------------------------------------------------------
        for action_id in actions:
            exists = UserScreenPermission.objects.filter(
                usertype_id_id=usertype_id,
                staffusertype_id_id=staffusertype_id,
                userscreen_id_id=userscreen_id,
                userscreenaction_id_id=action_id,
                is_deleted=False
            ).exists()

            if exists:
                skipped.append({
                    "action": action_id,
                    "reason": (
                        "Permission already exists for this specific role "
                        f"(usertype={usertype_id}, staffusertype={staffusertype_id})"
                    )
                })
                continue

            obj = UserScreenPermission.objects.create(
                usertype_id_id=usertype_id,
                staffusertype_id_id=staffusertype_id,
                mainscreen_id_id=mainscreen_id,
                userscreen_id_id=userscreen_id,
                userscreenaction_id_id=action_id,
                description=description,
                order_no=order_no
            )

            created_objs.append(obj)
            order_no += 1

        return {
            "created": created_objs,
            "skipped": skipped
        }
