from rest_framework import serializers
from .apps.continent import Continent
from .apps.country import Country
from .apps.state import State
from .apps.district import District
from .apps.city import City
from .apps.zone import Zone
from .apps.ward import Ward
from .apps.fuel import Fuel
from .apps.property import Property
from .apps.userpermission import UserPermission
from .apps.userType import UserType
from .apps.mainuserscreen import MainUserScreen
from .apps.userType import UserType
from .apps.userCreation import User
from .apps.vehicleTypeCreation import VehicleTypeCreation
from .apps.vehicleCreation import VehicleCreation
from .apps.complaints import Complaint





from .models import SubProperty
from .models import CustomerCreation
from .models import WasteCollection
from .models import FeedBack

from .models import (
    MainUserScreen,
    UserScreen,
    UserType,
    UserPermission,
)

class ContinentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Continent
        fields = '__all__'

class CountrySerializer(serializers.ModelSerializer):
    # This line automatically pulls the continent's name from the related model
    continent_name = serializers.CharField(source='continent.name', read_only=True)

    class Meta:
        model = Country
        fields = '__all__'


class StateSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)
    class Meta:
        model = State
        fields = '__all__'
        
class DistrictSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)
    state_name = serializers.CharField(source='state.name', read_only=True)
    class Meta:
        model = District
        fields = '__all__'
        
class CitySerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)
    state_name = serializers.CharField(source='state.name', read_only=True)
    district_name = serializers.CharField(source='district.name', read_only=True)

    class Meta:
        model = City
        fields = '__all__'

    def validate(self, attrs):
        district = attrs.get("district")
        name = attrs.get("name")
        instance = getattr(self, "instance", None)

        # Prevent duplicates for same district (ignore soft-deleted cities)
        qs = City.objects.filter(
            district=district,
            name__iexact=name.strip(),
            is_deleted=False
        )
        if instance:
            qs = qs.exclude(pk=instance.pk)

        if qs.exists():
            raise serializers.ValidationError({
                "name": "City name already exists for the selected district."
            })

        return attrs
        
class ZoneSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)
    state_name = serializers.CharField(source='state.name', read_only=True)
    district_name = serializers.CharField(source='district.name', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)

    class Meta:
        model = Zone
        fields = '__all__'
    def validate(self, attrs):
        city = attrs.get("city")
        name = attrs.get("name")
        instance = getattr(self, "instance", None)

        # Check only for non-deleted duplicates
        qs = Zone.objects.filter(city=city, name__iexact=name.strip(), is_deleted=False)
        if instance:
            qs = qs.exclude(pk=instance.pk)

        if qs.exists():
            raise serializers.ValidationError({
                "name": "Zone name already exists for the selected city."
            })
        return attrs
     
class WardSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)
    state_name = serializers.CharField(source='state.name', read_only=True)
    district_name = serializers.CharField(source='district.name', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)
    zone_name = serializers.CharField(source='zone.name', read_only=True)

    class Meta:
        model = Ward
        fields = '__all__'

    def validate(self, attrs):
        """
        Enforce uniqueness of Ward `name` within its geographic scope,
        ignoring soft-deleted rows. Scope priority:
        zone → city → district → state → country.
        """
        instance = getattr(self, "instance", None)

        # Pull current values (support partial updates)
        def cur(field):
            return attrs.get(field, getattr(instance, field) if instance else None)

        name = (attrs.get("name") or (instance.name if instance else "")).strip()
        country = cur("country")
        state = cur("state")
        district = cur("district")
        city = cur("city")
        zone = cur("zone")

        if not name:
            return attrs  # let default 'required' errors handle empty name

        qs = Ward.objects.filter(is_deleted=False, name__iexact=name)

        # Scope filters: match exactly on whichever geography fields are present,
        # and require NULL match for fields not provided to avoid cross-scope clashes.
        scope_filters = {
            "country": country,
            "state": state,
            "district": district,
            "city": city,
            "zone": zone,
        }
        for field, value in scope_filters.items():
            if value is not None:
                qs = qs.filter(**{f"{field}": value})
            else:
                qs = qs.filter(**{f"{field}__isnull": True})

        if instance:
            qs = qs.exclude(pk=instance.pk)

        if qs.exists():
            raise serializers.ValidationError({
                "name": "Ward name already exists in the selected scope."
            })

        return attrs
    
class FuelSerializer(serializers.ModelSerializer):
   
    class Meta:
        model = Fuel
        fields = '__all__'
        
class PropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = '__all__'
        

class SubPropertySerializer(serializers.ModelSerializer):
    property_name = serializers.CharField(source="property.property_name", read_only=True)

    class Meta:
        model = SubProperty
        fields = "__all__"
        
class CustomerCreationSerializer(serializers.ModelSerializer):
    ward_name = serializers.CharField(source="ward.name", read_only=True)
    zone_name = serializers.CharField(source="zone.name", read_only=True)
    city_name = serializers.CharField(source="city.name", read_only=True)
    district_name = serializers.CharField(source="district.name", read_only=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    country_name = serializers.CharField(source="country.name", read_only=True)
    property_name = serializers.CharField(source="property.property_name", read_only=True)
    sub_property_name = serializers.CharField(source="sub_property.sub_property_name", read_only=True)

    class Meta:
        model = CustomerCreation
        fields = "__all__"
        
class WasteCollectionSerializer(serializers.ModelSerializer):
    # Pull all geo and customer data via CustomerCreation relation
    ward_name = serializers.CharField(source="customer.ward.ward_name", read_only=True)
    zone_name = serializers.CharField(
        source="customer.zone.name", read_only=True, default=None
    )
    city_name = serializers.CharField(source="customer.city.name", read_only=True)
    district_name = serializers.CharField(source="customer.district.name", read_only=True)
    state_name = serializers.CharField(source="customer.state.name", read_only=True)
    country_name = serializers.CharField(source="customer.country.name", read_only=True)
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)
    contact_no = serializers.CharField(source="customer.contact_no", read_only=True)
    building_no = serializers.CharField(source="customer.building_no", read_only=True)
    street = serializers.CharField(source="customer.street", read_only=True)
    area = serializers.CharField(source="customer.area", read_only=True)
    pincode = serializers.CharField(source="customer.pincode", read_only=True)
    latitude = serializers.CharField(source="customer.latitude", read_only=True)
    longitude = serializers.CharField(source="customer.longitude", read_only=True)
    id_proof_type = serializers.CharField(source="customer.id_proof_type", read_only=True)
    id_no = serializers.CharField(source="customer.id_no", read_only=True)
    qr_code = serializers.CharField(source="customer.qr_code", read_only=True)
    is_active_customer = serializers.BooleanField(source="customer.is_active", read_only=True)

    class Meta:
        model = WasteCollection
        fields = [
            "id",
            "unique_id",
            "customer",
            "customer_name",
            "contact_no",
            "building_no",
            "street",
            "area",
            "pincode",
            "latitude",
            "longitude",
            "id_proof_type",
            "id_no",
            "qr_code",
            "is_active_customer",
            "ward_name",
            "zone_name",
            "city_name",
            "district_name",
            "state_name",
            "country_name",
            "wet_waste",
            "dry_waste",
            "mixed_waste",
            "total_quantity",
            "collection_date",
            "collection_time",
            "is_deleted",
            "is_active",
        ]
              
class FeedBackSerializer(serializers.ModelSerializer):
    # Pull all geo and customer data via CustomerCreation relation
    ward_name = serializers.CharField(source="customer.ward.ward_name", read_only=True)
    zone_name = serializers.CharField(
        source="customer.zone.name", read_only=True, default=None
    )
    city_name = serializers.CharField(source="customer.city.name", read_only=True)
    district_name = serializers.CharField(source="customer.district.name", read_only=True)
    state_name = serializers.CharField(source="customer.state.name", read_only=True)
    country_name = serializers.CharField(source="customer.country.name", read_only=True)
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)
    contact_no = serializers.CharField(source="customer.contact_no", read_only=True)
    building_no = serializers.CharField(source="customer.building_no", read_only=True)
    street = serializers.CharField(source="customer.street", read_only=True)
    area = serializers.CharField(source="customer.area", read_only=True)
    pincode = serializers.CharField(source="customer.pincode", read_only=True)
    latitude = serializers.CharField(source="customer.latitude", read_only=True)
    longitude = serializers.CharField(source="customer.longitude", read_only=True)
    id_proof_type = serializers.CharField(source="customer.id_proof_type", read_only=True)
    id_no = serializers.CharField(source="customer.id_no", read_only=True)
    qr_code = serializers.CharField(source="customer.qr_code", read_only=True)
    is_active_customer = serializers.BooleanField(source="customer.is_active", read_only=True)

    class Meta:
        model = FeedBack
        fields = [
            "id",
            "unique_id",
            "customer",
            "customer_name",
            "contact_no",
            "building_no",
            "street",
            "area",
            "pincode",
            "latitude",
            "longitude",
            "id_proof_type",
            "id_no",
            "qr_code",
            "is_active_customer",
            "ward_name",
            "zone_name",
            "city_name",
            "district_name",
            "state_name",
            "country_name",
            "category",
            "feedback_details",
            "is_deleted",
            "is_active",
        ]

class UserTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserType
        fields = '__all__'

class UserSerializer(serializers.ModelSerializer):
    user_type = serializers.PrimaryKeyRelatedField(queryset=UserType.objects.all())

    class Meta:
        model = User
        fields = '__all__'

class VehicleTypeCreationSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleTypeCreation
        fields = '__all__'


class VehicleCreationSerializer(serializers.ModelSerializer):
    vehicle_type_name = serializers.CharField(source='vehicle_type.vehicleType', read_only=True)
    fuel_type_name = serializers.CharField(source='fuel_type', read_only=True)
    zone_name = serializers.CharField(source='zone.name', read_only=True)
    ward_name = serializers.CharField(source='ward.name', read_only=True)

    class Meta:
        model = VehicleCreation
        fields = "__all__"




class ComplaintSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)
    zone_name = serializers.CharField(source="zone.name", read_only=True)
    ward_name = serializers.CharField(source="ward.name", read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Complaint
        fields = "__all__"

    def get_image_url(self, obj):
        request = self.context.get("request")
        if obj.image and hasattr(obj.image, "url"):
            return request.build_absolute_uri(obj.image.url)
        return None

class MainUserScreenSerializer(serializers.ModelSerializer):
    class Meta:
        model = MainUserScreen
        fields = "__all__"

class UserScreenSerializer(serializers.ModelSerializer):
    mainscreen_name = serializers.CharField(source="mainscreen.mainscreen", read_only=True)

    class Meta:
        model = UserScreen
        fields = "__all__"


class UserPermissionSerializer(serializers.ModelSerializer):
    user_type_name = serializers.SerializerMethodField()
    main_screen_name = serializers.SerializerMethodField()
    user_screen_name = serializers.SerializerMethodField()

    class Meta:
        model = UserPermission
        fields = [
            "id",
            "unique_id",
            "user_type",
            "user_type_name",
            "main_screen",
            "main_screen_name",
            "user_screen",
            "user_screen_name",
            "permissions",
            "is_active",
            "is_delete"
        ]

    def get_user_type_name(self, obj):
        return obj.user_type.name if obj.user_type else None

    def get_main_screen_name(self, obj):
        return obj.main_screen.mainscreen if obj.main_screen else None

    def get_user_screen_name(self, obj):
        return obj.user_screen.screen_name if obj.user_screen else None
