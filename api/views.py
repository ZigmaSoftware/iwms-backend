from rest_framework.response import Response
from rest_framework import viewsets, status
from django.db import transaction
from .apps.userType import UserType
from .apps.userCreation import User
from .apps.vehicleTypeCreation import VehicleTypeCreation
from .apps.vehicleCreation import VehicleCreation
from .apps.complaints import Complaint
from .apps.continent import Continent
from .apps.country import Country
from .apps.state import State
from .apps.district import District
from .apps.city import City
from .apps.zone import Zone
from .apps.ward import Ward
from .apps.fuel import Fuel
from .apps.property import Property
from .apps.subproperty import SubProperty
from .apps.customercreation import CustomerCreation
from .apps.wastecollection import WasteCollection
from .apps.feedback import FeedBack
from .models import UserScreen
from .apps.mainuserscreen import MainUserScreen
from .apps.userscreen import UserScreen
from .apps.userpermission import UserPermission



from .serializers import (
    ContinentSerializer,
    CountrySerializer,
    StateSerializer,
    DistrictSerializer,
    CitySerializer,
    ZoneSerializer,
    WardSerializer,
    FuelSerializer,
    PropertySerializer,
    SubPropertySerializer,
    CustomerCreationSerializer,
    WasteCollectionSerializer,
    FeedBackSerializer,
    UserTypeSerializer,
    UserSerializer,
    VehicleTypeCreationSerializer,
    VehicleCreationSerializer,
    ComplaintSerializer,
    MainUserScreenSerializer,
    UserScreenSerializer,
    UserPermissionSerializer,
)


#  Continent
class ContinentViewSet(viewsets.ModelViewSet):
    queryset = Continent.objects.filter(is_active=True)
    serializer_class = ContinentSerializer


# 🇮🇳 Country
class CountryViewSet(viewsets.ModelViewSet):
    queryset = Country.objects.filter(is_active=True)
    serializer_class = CountrySerializer


# State
class StateViewSet(viewsets.ModelViewSet):
    queryset = State.objects.all()
    serializer_class = StateSerializer

    def get_queryset(self):
        queryset = State.objects.filter(is_deleted=False)
        country_id = self.request.query_params.get("country")  # filter by country
        if country_id:
            queryset = queryset.filter(country_id=country_id)
        return queryset


# District
class DistrictViewSet(viewsets.ModelViewSet):
    queryset = District.objects.all()
    serializer_class = DistrictSerializer

    def get_queryset(self):
        queryset = District.objects.filter(is_deleted=False)
        state_id = self.request.query_params.get("state")  #  filter by state
        if state_id:
            queryset = queryset.filter(state_id=state_id)
        return queryset

# City
class CityViewSet(viewsets.ModelViewSet):
    queryset = City.objects.all()
    serializer_class = CitySerializer

    def get_queryset(self):
         # Base queryset: only active and not deleted cities
        queryset = City.objects.filter(is_deleted=False)
        
         # Extract query parameters
        district_id = self.request.query_params.get("district")
        state_id = self.request.query_params.get("state")
        country_id = self.request.query_params.get("country")

        #  Flexible filtering (district → state → country)
        if district_id:
            queryset = queryset.filter(district_id=district_id)
        elif state_id:
            queryset = queryset.filter(state_id=state_id)
        elif country_id:
            queryset = queryset.filter(country_id=country_id)
        return queryset

# Zone
class ZoneViewSet(viewsets.ModelViewSet):
    queryset = Zone.objects.all() 
    serializer_class = ZoneSerializer

    def get_queryset(self):
        # Base queryset: only active and not deleted zones
        queryset = Zone.objects.filter(is_deleted=False)

        # Extract query parameters
        city_id = self.request.query_params.get("city")
        district_id = self.request.query_params.get("district")
        state_id = self.request.query_params.get("state")
        country_id = self.request.query_params.get("country")

        # Flexible filtering hierarchy: city → district → state → country
        if city_id:
            queryset = queryset.filter(city_id=city_id)
        elif district_id:
            queryset = queryset.filter(district_id=district_id)
        elif state_id:
            queryset = queryset.filter(state_id=state_id)
        elif country_id:
            queryset = queryset.filter(country_id=country_id)

        return queryset


#  Ward


class WardViewSet(viewsets.ModelViewSet):
    queryset = Ward.objects.filter(is_deleted=False)
    serializer_class = WardSerializer

    def get_queryset(self):
        # Base queryset: only active and not deleted wards (toggleable via query)
        queryset = Ward.objects.filter(is_deleted=False)

        # Extract query parameters
        zone_id = self.request.query_params.get("zone")
        city_id = self.request.query_params.get("city")
        district_id = self.request.query_params.get("district")
        state_id = self.request.query_params.get("state")
        country_id = self.request.query_params.get("country")
        is_active = self.request.query_params.get("is_active")  # optional: "1"/"0"/"true"/"false"

        # Flexible filtering hierarchy: zone → city → district → state → country
        if zone_id:
            queryset = queryset.filter(zone_id=zone_id)
        elif city_id:
            queryset = queryset.filter(city_id=city_id)
        elif district_id:
            queryset = queryset.filter(district_id=district_id)
        elif state_id:
            queryset = queryset.filter(state_id=state_id)
        elif country_id:
            queryset = queryset.filter(country_id=country_id)

        # Optional active flag filter (defaults to all active+inactive unless specified)
        if is_active is not None:
            truthy = {"1", "true", "True", "TRUE"}
            falsy = {"0", "false", "False", "FALSE"}
            if is_active in truthy:
                queryset = queryset.filter(is_active=True)
            elif is_active in falsy:
                queryset = queryset.filter(is_active=False)

        return queryset
    
class FuelViewSet(viewsets.ModelViewSet):
    queryset = Fuel.objects.filter(is_deleted=False)
    serializer_class = FuelSerializer

class PropertyViewSet(viewsets.ModelViewSet):
    queryset = Property.objects.filter(is_deleted=False)
    serializer_class = PropertySerializer
    
class SubPropertyViewSet(viewsets.ModelViewSet):
    queryset = SubProperty.objects.filter(is_deleted=False).select_related("property").order_by("sub_property_name")
    serializer_class = SubPropertySerializer
    
class CustomerCreationViewSet(viewsets.ModelViewSet):
    queryset = (
        CustomerCreation.objects
        .filter(is_deleted=False)
        .select_related(
            "ward", "zone", "city", "district", "state",
            "country", "property", "sub_property"
        )
        .order_by("customer_name")
    )
    serializer_class = CustomerCreationSerializer

class WasteCollectionViewSet(viewsets.ModelViewSet):
    queryset = (
        WasteCollection.objects
        .filter(is_deleted=False)
        .select_related(
            "customer__ward",
            "customer__zone",
            "customer__city",
            "customer__district",
            "customer__state",
            "customer__country",
            "customer__property",
            "customer__sub_property"
        )
        .order_by("-collection_date", "-collection_time")
    )
    serializer_class = WasteCollectionSerializer
    

class FeedBackViewSet(viewsets.ModelViewSet):
    queryset = (
        FeedBack.objects
        .filter(is_deleted=False)
        .select_related(
            "customer__ward",
            "customer__zone",
            "customer__city",
            "customer__district",
            "customer__state",
            "customer__country",
            "customer__property",
            "customer__sub_property"
        )
    )
    serializer_class = FeedBackSerializer
    

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.filter(is_delete=False)
    serializer_class = UserSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_delete = True
        instance.save()
        return Response({"message": "User soft deleted successfully"}, status=status.HTTP_200_OK)



class VehicleTypeCreationViewSet(viewsets.ModelViewSet):
    queryset = VehicleTypeCreation.objects.filter(is_delete=False)
    serializer_class = VehicleTypeCreationSerializer


class UserTypeViewSet(viewsets.ModelViewSet):
    queryset = UserType.objects.filter(is_delete=False)
    serializer_class = UserTypeSerializer


class VehicleCreationViewSet(viewsets.ModelViewSet):
    queryset = VehicleCreation.objects.filter(is_deleted=False)
    serializer_class = VehicleCreationSerializer



class ComplaintViewSet(viewsets.ModelViewSet):
    serializer_class = ComplaintSerializer
    queryset = Complaint.objects.filter(is_deleted=False).select_related("customer", "zone", "ward")
    
    

    def get_queryset(self):
        queryset = Complaint.objects.filter(is_deleted=False)
        customer_id = self.request.query_params.get("customer_id") or self.request.query_params.get("customer")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        return queryset

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.save()
        return Response(
            {"message": "Complaint soft deleted successfully"},
            status=status.HTTP_200_OK,
        )                            


class MainUserScreenViewSet(viewsets.ModelViewSet):
    queryset = MainUserScreen.objects.filter(is_active=True)
    serializer_class = MainUserScreenSerializer


class UserScreenViewSet(viewsets.ModelViewSet):
    serializer_class = UserScreenSerializer
    queryset = UserScreen.objects.filter(is_delete=False).select_related("mainscreen")

    def get_queryset(self):
        queryset = super().get_queryset()
        mainscreen_param = (
            self.request.query_params.get("mainscreen")
            or self.request.query_params.get("main_screen")
        )

        if mainscreen_param:
            queryset = queryset.filter(mainscreen_id=mainscreen_param)

        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.is_delete = True
        instance.save(update_fields=["is_active", "is_delete"])
        return Response({"message": "Screen deleted successfully"}, status=status.HTTP_200_OK)



class UserPermissionViewSet(viewsets.ModelViewSet):
    # show only active permissions everywhere
    queryset = UserPermission.objects.filter(is_delete=False)
    serializer_class = UserPermissionSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        data = request.data

        
        if isinstance(data, list):
            saved_records = []
            for item in data:
                user_type_id = item.get("user_type")
                main_screen_id = item.get("main_screen")
                user_screen_id = item.get("user_screen")

                # Update if exists, else create
                obj, created = UserPermission.objects.update_or_create(
                    user_type_id=user_type_id,
                    main_screen_id=main_screen_id,
                    user_screen_id=user_screen_id,
                    defaults={
                        "permissions": item.get("permissions", {}),
                        "is_active": item.get("is_active", True),
                        "is_delete": item.get("is_delete", False),
                    },
                )
                saved_records.append(obj)

            serializer = self.get_serializer(saved_records, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        item = data
        user_type_id = item.get("user_type")
        main_screen_id = item.get("main_screen")
        user_screen_id = item.get("user_screen")

        obj, created = UserPermission.objects.update_or_create(
            user_type_id=user_type_id,
            main_screen_id=main_screen_id,
            user_screen_id=user_screen_id,
            defaults={
                "permissions": item.get("permissions", {}),
                "is_active": item.get("is_active", True),
                "is_delete": item.get("is_delete", False),
            },
        )

        serializer = self.get_serializer(obj)
        return Response(serializer.data, status=status.HTTP_200_OK)

 
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.is_delete = True
        instance.save(update_fields=["is_active", "is_delete"])
        return Response({"message": "Deleted successfully"}, status=status.HTTP_200_OK)
