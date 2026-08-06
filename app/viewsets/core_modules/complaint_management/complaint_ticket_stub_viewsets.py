from rest_framework import viewsets
from rest_framework.response import Response


class ComplaintTicketStubViewSet(viewsets.ViewSet):
    """
    Placeholder for a complaint-ticket sub-resource that exists in the
    government reference app (app/viewsets/core_modules/complaint_management/
    master_viewsets.py) but has no backing model/serializer here yet.

    `list` returns an empty array so frontend list screens render without
    erroring; every other action responds 501 until a real model +
    serializer + viewset replace this stub.
    """

    permission_resource = None  # set per subclass below

    def list(self, request, *args, **kwargs):
        return Response([])

    def retrieve(self, request, *args, **kwargs):
        return self._not_implemented()

    def create(self, request, *args, **kwargs):
        return self._not_implemented()

    def update(self, request, *args, **kwargs):
        return self._not_implemented()

    def partial_update(self, request, *args, **kwargs):
        return self._not_implemented()

    def destroy(self, request, *args, **kwargs):
        return self._not_implemented()

    def _not_implemented(self):
        return Response(
            {"detail": f"{self.permission_resource or self.__class__.__name__} is not implemented yet."},
            status=501,
        )


class ComplaintModuleViewSet(ComplaintTicketStubViewSet):
    permission_resource = "ComplaintModule"


class ComplaintPriorityViewSet(ComplaintTicketStubViewSet):
    permission_resource = "ComplaintPriority"


class ComplaintStatusViewSet(ComplaintTicketStubViewSet):
    permission_resource = "ComplaintStatus"


class ComplaintSourceViewSet(ComplaintTicketStubViewSet):
    permission_resource = "ComplaintSource"


class ComplaintLanguageViewSet(ComplaintTicketStubViewSet):
    permission_resource = "ComplaintLanguage"


class ComplaintTeamViewSet(ComplaintTicketStubViewSet):
    permission_resource = "ComplaintTeam"


class ComplaintSlaRuleViewSet(ComplaintTicketStubViewSet):
    permission_resource = "ComplaintSlaRule"


class ComplaintRoutingRuleViewSet(ComplaintTicketStubViewSet):
    permission_resource = "ComplaintRoutingRule"


class ComplaintFeedbackViewSet(ComplaintTicketStubViewSet):
    permission_resource = "ComplaintFeedback"


class ComplaintReopenHistoryViewSet(ComplaintTicketStubViewSet):
    permission_resource = "ComplaintReopenHistory"


class ComplaintNotificationViewSet(ComplaintTicketStubViewSet):
    permission_resource = "ComplaintNotification"


class ComplaintAddressChangeViewSet(ComplaintTicketStubViewSet):
    permission_resource = "ComplaintAddressChange"
