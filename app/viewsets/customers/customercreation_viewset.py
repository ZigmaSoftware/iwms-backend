# import re

# from django.db.models import Q, Count
# from django.db.models.functions import Upper
# from rest_framework import request, status
# from rest_framework.decorators import action
# from rest_framework.response import Response

# from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
# from app.models.customers.customercreation import CustomerCreation
# from app.models.superadmin_masters.project import Project
# from app.models.waste_types.subproperty import SubProperty
# from app.serializers.customers.customercreation_serializer import CustomerCreationSerializer


# from app.utils.customer_qr import generate_customer_qr_content, generate_apartment_qr_data

# PROPERTY_GROUPING = {
#     "apartment": {
#         "apartment_name_display": "apartment_name",
#         "block_display": "block_no",
#     },
#     "villa": {
#         "villa_number": "villa_no",
#     },
#     "individual_house": {
#         "building_number": "building_no",
#     },
# }


# RESERVED_QUERY_PARAMS = {
#     "subproperty", "sub_property", "property", "property_id",
#     "sub_property_id", "subproperty_id", "project",
#     "format", "search", "ordering", "page", "page_size",
#     "limit", "offset",
# }


# def _normalize_key(value):
#     normalized = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower())
#     return normalized.strip("_")


# def normalize(value):
#     return (value or "").strip().upper()


# def _candidate_subproperty_names(subproperty_key):
#     tokens = [token for token in subproperty_key.split("_") if token]
#     if not tokens:
#         return set()

#     return {
#         " ".join(tokens),
#         "_".join(tokens),
#         "-".join(tokens),
#         "".join(tokens),
#         " ".join(tokens).title(),
#     }


# def _build_dynamic_filter_aliases():
#     aliases = {}

#     for grouping in PROPERTY_GROUPING.values():
#         for model_field in grouping.values():
#             aliases[model_field] = model_field
#             if model_field.endswith("_no"):
#                 aliases[model_field.replace("_no", "_number")] = model_field

#     aliases["block"] = "block_no"
#     aliases["apartment_name"] = "apartment_name"
#     aliases["flat_no"] = "flat_no"
#     aliases["villa_no"] = "villa_no"
#     aliases["building_no"] = "building_no"

#     return aliases


# DYNAMIC_FILTER_ALIASES = _build_dynamic_filter_aliases()





# from app.models.customers.customercreation import CustomerCreation

# def get_or_create_apartment_qr(apartment_name,company_id,request):
#     apartment_name = (apartment_name or "").strip().upper()

#     obj = CustomerCreation.objects.filter(
#         apartment_name__iexact=apartment_name,
#         company_id=company_id,
#         is_deleted=False
#     ).first()

#     if not obj:
#         return None

#     # already exists
#     if obj.apartment_qr:
#         return obj.apartment_qr.url

#     # generate QR
#     qr_data = generate_apartment_qr_data(apartment_name)
#     qr_file = generate_customer_qr_content(qr_data)

#     file_name = f"apartment_{apartment_name}.png".replace(" ", "_")

#     obj.apartment_qr.save(file_name, qr_file, save=True)

#     return obj.apartment_qr.url


# class CustomerCreationViewSet(CompanyScopedViewSet):
#     permission_resource = "CustomerCreation"
#     serializer_class = CustomerCreationSerializer
#     lookup_field = "unique_id"

#     queryset = (
#         CustomerCreation.objects
#         .filter(is_deleted=False)
#         .select_related(
#             "company_id", "project_id", "ward", "zone", "city",
#             "district", "state", "country", "panchayat_id",
#             "property_ref", "sub_property",
#         )
#         .order_by("customer_name")
#     )

#     # -----------------------------------------------------
#     # Subproperty Resolver
#     # -----------------------------------------------------

#     def _resolve_subproperty_context(self, raw_subproperty):
#         cleaned_value = (raw_subproperty or "").strip()
#         if not cleaned_value:
#             return None, ""

#         subproperty = SubProperty.objects.filter(
#             is_deleted=False
#         ).filter(
#             Q(unique_id__iexact=cleaned_value)
#             | Q(sub_property_name__iexact=cleaned_value)
#         ).first()

#         if subproperty:
#             return subproperty, _normalize_key(subproperty.sub_property_name)

#         normalized = _normalize_key(cleaned_value)

#         for row in SubProperty.objects.filter(is_deleted=False).only(
#             "unique_id",
#             "sub_property_name",
#         ):
#             if _normalize_key(row.sub_property_name) == normalized:
#                 return row, normalized

#         return None, normalized

#     # -----------------------------------------------------
#     # Apartment Count
#     # -----------------------------------------------------

#     @action(detail=False, methods=["get"], url_path="apartment-count")
#     def apartment_count(self, request):
#         queryset = self.filter_queryset(self.get_queryset())

#         company_id = request.query_params.get("company_id")
#         if company_id:
#             queryset = queryset.filter(company_id__unique_id=company_id)
       
#         data = (
#             queryset
#             .exclude(apartment_name__isnull=True)
#             .exclude(apartment_name="")
#             .exclude(block_no__isnull=True)
#             .exclude(block_no="")
#             .exclude(flat_no__isnull=True)
#             .exclude(flat_no="")
#             .annotate(apartment_name_upper=Upper("apartment_name"))
#             .values("apartment_name_upper")
#             .annotate(
#                 user_count=Count("unique_id"),
#                 block_count=Count("block_no", distinct=True),
#                 flat_count=Count("unique_id"),
#             )
#             .order_by("apartment_name_upper")
#         )

#         response_data = []

#         for item in data:
#             apartment_name = item["apartment_name_upper"]

#             qr_url = get_or_create_apartment_qr(apartment_name,request.user.company_id,request)

#             if qr_url:
#                 qr_url = request.build_absolute_uri(qr_url)

#             response_data.append({
#                 "apartment_name": apartment_name,
#                 "user_count": item["user_count"],
#                 "block_count": item["block_count"],
#                 "flat_count": item["flat_count"],
#                 "qr_code": qr_url,  # ✅ NEW FIELD
#             })

#         return Response(response_data)

#     # -----------------------------------------------------
#     # Block Count
#     # -----------------------------------------------------

#     @action(detail=False, methods=["get"], url_path="block-count")
#     def block_count(self, request):
#         apartment_name = request.query_params.get("apartment_name")

#         if not apartment_name:
#             return Response({"error": "apartment_name is required"}, status=400)

#         queryset = self.filter_queryset(self.get_queryset()).filter(
#             apartment_name__iexact=apartment_name.strip()
#         )

#         company_id = request.query_params.get("company_id")

#         if company_id:
#             queryset = queryset.filter(company_id__unique_id=company_id)

#         data = (
#             queryset.exclude(block_no__isnull=True)
#             .exclude(block_no="")
#             .values("block_no")
#             .annotate(flat_count=Count("unique_id"))
#             .order_by("block_no")
#         )

#         return Response(list(data))

#     # -----------------------------------------------------
#     # Flat Count
#     # -----------------------------------------------------

#     @action(detail=False, methods=["get"], url_path="flat-count")
#     def flat_count(self, request):
#         apartment_name = request.query_params.get("apartment_name")
#         block = request.query_params.get("block")

#         if not apartment_name or not block:
#             return Response(
#                 {"error": "apartment_name and block are required"},
#                 status=400
#             )

#         queryset = self.filter_queryset(self.get_queryset()).filter(
#             apartment_name__iexact=apartment_name.strip(),
#             block_no__iexact=block.strip()
#         )

#         company_id = request.query_params.get("company_id")

#         if company_id:
#             queryset = queryset.filter(company_id__unique_id=company_id)

#         data = (
#             queryset.exclude(flat_no__isnull=True)
#             .exclude(flat_no="")
#             .values("flat_no")
#             .annotate(user_count=Count("unique_id"))
#             .order_by("flat_no")
#         )

#         return Response(list(data))

#     # -----------------------------------------------------
#     # Property User Count (FIXED ✅)
#     # -----------------------------------------------------

#     @action(detail=False, methods=["get"], url_path="property-user-count")
#     def property_user_count(self, request):
#         subproperty_value = request.query_params.get("subproperty")

#         if not subproperty_value:
#             return Response({"error": "subproperty is required"}, status=400)

#         subproperty_obj, subproperty_key = self._resolve_subproperty_context(
#             subproperty_value
#         )

#         grouping = PROPERTY_GROUPING.get(subproperty_key)
#         if not grouping:
#             return Response({"error": "Invalid subproperty"}, status=400)

#         queryset = self.filter_queryset(self.get_queryset())

#         # ✅ filter by subproperty
#         if subproperty_obj:
#             queryset = queryset.filter(sub_property=subproperty_obj)

#         # ✅ APPLY DYNAMIC FILTERS (MAIN FIX)
#         for param, value in request.query_params.items():
#             if param in RESERVED_QUERY_PARAMS:
#                 continue

#             model_field = DYNAMIC_FILTER_ALIASES.get(param)

#             if model_field and value:
#                 queryset = queryset.filter(**{
#                     f"{model_field}__iexact": value.strip()
#                 })

#         # ✅ remove null/empty values
#         for field in grouping.values():
#             queryset = queryset.exclude(**{f"{field}__isnull": True}).exclude(
#                 **{field: ""}
#             )

#         grouped_data = {}

#         for obj in queryset:
#             group_key = tuple(
#                 normalize(getattr(obj, field))
#                 for field in grouping.values()
#             )

#             if group_key not in grouped_data:
#                 grouped_data[group_key] = {
#                     **{
#                         key: getattr(obj, field)
#                         for key, field in grouping.items()
#                     },
#                     "user_count": 0,
#                     "users": []
#                 }

#             user_data = {
#                 "customer_name": obj.customer_name,
#                 "contact_no": obj.contact_no,
#             }

#             if obj.flat_no:
#                 user_data["flat_no"] = obj.flat_no

#             grouped_data[group_key]["users"].append(user_data)
#             grouped_data[group_key]["user_count"] += 1

#         return Response(list(grouped_data.values()))


import re
import csv
import io

from django.db.models import Q, Count
from django.db.models.functions import Upper
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.customers.customercreation import CustomerCreation
from app.models.superadmin_masters.project import Project
from app.models.waste_types.subproperty import SubProperty
from app.models.common_masters.state import State
from app.models.common_masters.country import Country
from app.models.waste_types.property import Property

from app.serializers.customers.customercreation_serializer import CustomerCreationSerializer

from app.utils.customer_qr import generate_customer_qr_content, generate_apartment_qr_data

PROPERTY_GROUPING = {
    "apartment": {
        "apartment_name_display": "apartment_name",
        "block_display": "block_no",
    },
    "villa": {
        "villa_number": "villa_no",
    },
    "individual_house": {
        "building_number": "building_no",
    },
}

RESERVED_QUERY_PARAMS = {
    "subproperty", "sub_property", "property", "property_id",
    "sub_property_id", "subproperty_id", "project",
    "format", "search", "ordering", "page", "page_size",
    "limit", "offset",
}


def normalize(value):
    return (value or "").strip().upper()


class CustomerCreationViewSet(CompanyScopedViewSet):
    permission_resource = "CustomerCreation"
    serializer_class = CustomerCreationSerializer
    lookup_field = "unique_id"
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    queryset = (
        CustomerCreation.objects
        .filter(is_deleted=False)
        .select_related(
            "company_id", "project_id", "ward", "zone", "city",
            "district", "state", "country", "panchayat_id",
            "property_ref", "sub_property",
        )
        .order_by("customer_name")
    )

    # -----------------------------------------------------
    # Apartment Count
    # -----------------------------------------------------

    @action(detail=False, methods=["get"], url_path="apartment-count")
    def apartment_count(self, request):
        queryset = self.filter_queryset(self.get_queryset())

        company_id = request.query_params.get("company_id")
        if company_id:
            queryset = queryset.filter(company_id__unique_id=company_id)

        data = (
            queryset
            .exclude(apartment_name__isnull=True)
            .exclude(apartment_name="")
            .exclude(block_no__isnull=True)
            .exclude(block_no="")
            .exclude(flat_no__isnull=True)
            .exclude(flat_no="")
            .annotate(apartment_name_upper=Upper("apartment_name"))
            .values("apartment_name_upper")
            .annotate(
                user_count=Count("unique_id"),
                block_count=Count("block_no", distinct=True),
                flat_count=Count("unique_id"),
            )
            .order_by("apartment_name_upper")
        )

        response_data = []

        for item in data:
            apartment_name = item["apartment_name_upper"]

            response_data.append({
                "apartment_name": apartment_name,
                "user_count": item["user_count"],
                "block_count": item["block_count"],
                "flat_count": item["flat_count"],
            })

        return Response(response_data)

    # -----------------------------------------------------
    # Block Count
    # -----------------------------------------------------

    @action(detail=False, methods=["get"], url_path="block-count")
    def block_count(self, request):
        apartment_name = request.query_params.get("apartment_name")

        if not apartment_name:
            return Response({"error": "apartment_name is required"}, status=400)

        queryset = self.filter_queryset(self.get_queryset()).filter(
            apartment_name__iexact=apartment_name.strip()
        )

        data = (
            queryset.exclude(block_no__isnull=True)
            .exclude(block_no="")
            .values("block_no")
            .annotate(flat_count=Count("unique_id"))
            .order_by("block_no")
        )

        return Response(list(data))

    # -----------------------------------------------------
    # Flat Count
    # -----------------------------------------------------

    @action(detail=False, methods=["get"], url_path="flat-count")
    def flat_count(self, request):
        apartment_name = request.query_params.get("apartment_name")
        block = request.query_params.get("block")

        if not apartment_name or not block:
            return Response(
                {"error": "apartment_name and block are required"},
                status=400
            )

        queryset = self.filter_queryset(self.get_queryset()).filter(
            apartment_name__iexact=apartment_name.strip(),
            block_no__iexact=block.strip()
        )

        data = (
            queryset.exclude(flat_no__isnull=True)
            .exclude(flat_no="")
            .values("flat_no")
            .annotate(user_count=Count("unique_id"))
            .order_by("flat_no")
        )

        return Response(list(data))

    # -----------------------------------------------------
    # Property User Count
    # -----------------------------------------------------

    @action(detail=False, methods=["get"], url_path="property-user-count")
    def property_user_count(self, request):
        subproperty_value = request.query_params.get("subproperty")

        if not subproperty_value:
            return Response({"error": "subproperty is required"}, status=400)

        queryset = self.filter_queryset(self.get_queryset())

        data = queryset.values("customer_name").annotate(
            user_count=Count("unique_id")
        )

        return Response(list(data))

    # =========================================================
    # ✅ BULK UPLOAD (NEW - ADDED ONLY)
    # =========================================================

    @action(detail=False, methods=["post"], url_path="bulk-upload")
    def bulk_upload(self, request):
        file = request.FILES.get("file")

        if not file:
            return Response({"error": "CSV file is required"}, status=400)

        def get_fk(model, field, value):
            if not value:
                return None

            value = str(value).strip()

            if value.isdigit():
                return model.objects.filter(unique_id=value).first()

            return model.objects.filter(**{f"{field}__iexact": value}).first()

        try:
            decoded_file = file.read().decode("utf-8")
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)

            success_count = 0
            errors = []

            for index, row in enumerate(reader, start=1):

                state = get_fk(State, "name", row.get("state_id"))
                country = get_fk(Country, "name", row.get("country_id"))
                property_obj = get_fk(Property, "property_name", row.get("property_id"))
                sub_property = get_fk(SubProperty, "sub_property_name", row.get("sub_property_id"))

                if not state:
                    errors.append({"row": index, "error": f"Invalid state: {row.get('state_id')}"})
                    continue

                data = {
                    "company_id": request.data.get("company_id"),
                    "project_id": request.data.get("project_id"),
                    "customer_name": row.get("customer_name"),
                    "contact_no": row.get("contact_no"),
                    "building_no": row.get("building_no"),
                    "street": row.get("street"),
                    "area": row.get("area"),
                    "apartment_name": row.get("apartment_name"),
                    "block_no": row.get("block_no"),
                    "flat_no": row.get("flat_no"),
                    "pincode": row.get("pincode"),
                    "latitude": row.get("latitude"),
                    "longitude": row.get("longitude"),

                    "state_id": state.unique_id if state else None,
                    "country_id": country.unique_id if country else None,
                    "property_id": property_obj.unique_id if property_obj else None,
                    "sub_property_id": sub_property.unique_id if sub_property else None,

                    "id_proof_type": row.get("id_proof_type"),
                    "id_no": row.get("id_no"),
                }

                serializer = self.get_serializer(data=data)

                if serializer.is_valid():
                    serializer.save()
                    success_count += 1
                else:
                    errors.append({
                        "row": index,
                        "error": serializer.errors
                    })

            return Response({
                "message": "Bulk upload completed",
                "success_count": success_count,
                "errors": errors
            })

        except Exception as e:
            return Response({"error": str(e)}, status=500)