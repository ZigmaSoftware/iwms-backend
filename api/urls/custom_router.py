from rest_framework.routers import DefaultRouter
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.reverse import reverse
from collections import OrderedDict


class GroupedRouter(DefaultRouter):
    """
    Custom DRF router that groups endpoints by module names.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_map = OrderedDict()

    def register_group(self, group, prefix, viewset, basename=None):
        """
        Register a viewset inside a named group.
        """
        if group not in self.group_map:
            self.group_map[group] = []

        base = basename or prefix.replace("/", "-")

        self.group_map[group].append({
            "prefix": prefix,
            "basename": base,
            "viewset": viewset
        })

        return super().register(prefix, viewset, basename=base)

    def get_api_root_view(self, api_urls=None):
        grouped = self.group_map

        class GroupedAPIRoot(APIView):
            _ignore_model_permissions = True

            def get(self, request, *args, **kwargs):
                data = OrderedDict()

                for group_name, items in grouped.items():
                    data[group_name] = OrderedDict()

                    for entry in items:
                        url_name = f"{entry['basename']}-list"

                        try:
                            url = reverse(url_name, request=request)
                        except Exception:
                            url = None

                        data[group_name][entry["prefix"]] = url

                return Response(data)

        return GroupedAPIRoot.as_view()

    def get_urls(self):
        urls = super().get_urls()
        # override default root
        urls[0].callback = self.get_api_root_view()
        return urls
