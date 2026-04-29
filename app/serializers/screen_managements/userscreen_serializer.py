from django.db import transaction
from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.screen_managements.userscreen import UserScreen


class UserScreenSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    mainscreen_name = serializers.CharField(
        source="mainscreen_id.mainscreen_name",
        read_only=True
    )
    mainscreentype_id = serializers.CharField(
        source="mainscreen_id.mainscreentype_id.unique_id",
        read_only=True
    )
    mainscreentype_name = serializers.CharField(
        source="mainscreen_id.mainscreentype_id.type_name",
        read_only=True
    )
    # Backend is source of truth for ordering; allow clients to omit this.
    order_no = serializers.IntegerField(required=False, allow_null=True)
    # UI no longer sends icon_name; derive it from userscreen_name if omitted.
    icon_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = UserScreen
        fields = "__all__"
        extra_kwargs = {
            "order_no": {"required": False, "allow_null": True},
            "icon_name": {"required": False, "allow_blank": True, "allow_null": True},
        }

    def _next_order_no(self, mainscreen_id):
        with transaction.atomic():
            last = (
                UserScreen.objects.select_for_update()
                .filter(mainscreen_id=mainscreen_id, is_deleted=False)
                .order_by("-order_no")
                .first()
            )
            return (last.order_no if last else 0) + 1

    def create(self, validated_data):
        if not validated_data.get("icon_name"):
            validated_data["icon_name"] = (validated_data.get("userscreen_name") or "").strip()
        if validated_data.get("order_no") in (None, ""):
            validated_data["order_no"] = self._next_order_no(validated_data.get("mainscreen_id"))
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "order_no" not in validated_data or validated_data.get("order_no") is None:
            validated_data.pop("order_no", None)
        if "icon_name" not in validated_data or validated_data.get("icon_name") in (None, ""):
            validated_data.pop("icon_name", None)
        return super().update(instance, validated_data)

    def validate(self, data):
        mainscreen = data.get("mainscreen_id") or getattr(self.instance, "mainscreen_id", None)
        order_no = data.get("order_no")

        if order_no is None:
            return data
        if mainscreen is None:
            return data

        queryset = UserScreen.objects.filter(
            mainscreen_id=mainscreen,
            order_no=order_no,
            is_deleted=False
        )

        if self.instance:
            queryset = queryset.exclude(unique_id=self.instance.unique_id)

        if queryset.exists():
            raise serializers.ValidationError({
                "order_no": "This order number already exists for this Main Screen."
            })

        return data
