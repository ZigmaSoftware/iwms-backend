from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.superadmin.common_masters.country import Country
from app.models.superadmin.common_masters.continent import Continent
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.validators.unique_name_validator import unique_name_validator

class CountrySerializer(serializers.ModelSerializer):
    # Write accepts the continent's unique_id or its name ("Asia"); read
    # returns the unique_id.
    continent_id = NameOrUniqueIdField(
        queryset=Continent.objects.filter(is_deleted=False),
        name_field="name",
    )
    # Read-only display of the continent's name for list columns / exports.
    # continent_id itself already carries the uid (single source of truth —
    # one DB column, no extra storage).
    continent_name = serializers.SerializerMethodField()

    class Meta:
        model = Country
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []

    def get_continent_name(self, obj):
        # continent_id is a CharField uid string, not a relation — a dotted
        # source like "continent_id.name" traverses into the string and
        # resolves to nothing. Look the continent up explicitly (same as
        # StateSerializer.get_continent_name). Older seeded rows stored the
        # continent *name* here instead of the uid — fall back to a name
        # match so they still display (0009 backfills them to uids).
        continent = self._resolve_continent(obj.continent_id)
        return continent.name if continent else None

    @staticmethod
    def _resolve_continent(continent_id):
        if not continent_id:
            return None
        continent = Continent.objects.filter(unique_id=continent_id).first()
        if continent is None:
            continent = Continent.objects.filter(name__iexact=str(continent_id).strip()).first()
        return continent

    def validate(self, attrs):
        return unique_name_validator(
            Model=Country,
            scope_fields=["continent_id"]
        )(self, attrs)
