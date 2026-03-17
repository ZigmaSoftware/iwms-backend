from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.screen_managements.mainscreen import MainScreen

class MainScreenSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    mainscreentype_name = serializers.CharField(
        source="mainscreentype_id.type_name",
        read_only=True
    )

    class Meta:
        model = MainScreen
        fields = "__all__"


    def validate(self, data):
        mainscreentype = data.get("mainscreentype_id")
        order_no = data.get("order_no")

        queryset = MainScreen.objects.filter(
            mainscreentype_id=mainscreentype,
            order_no=order_no,
            is_deleted=False
        )

        # Exclude current instance during update
        if self.instance:
            queryset = queryset.exclude(unique_id=self.instance.unique_id)

        if queryset.exists():
            raise serializers.ValidationError({
                "order_no": "This order number already exists for this Main Screen Type."
            })

        return data
