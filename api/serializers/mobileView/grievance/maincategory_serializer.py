from rest_framework import serializers
from api.apps.main_category_citizenGrievance import MainCategory


class MainCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MainCategory
        fields = "__all__"
