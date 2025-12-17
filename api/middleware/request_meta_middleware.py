# api/middleware/request_meta_middleware.py
class RequestMetaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.ip_address = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0]
            or request.META.get("REMOTE_ADDR")
        )
        request.user_agent = request.META.get("HTTP_USER_AGENT", "")
        return self.get_response(request)
