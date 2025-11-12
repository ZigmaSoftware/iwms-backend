# import json
# import requests
# from django.conf import settings
# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.views.decorators.http import require_POST

# # ✅ Always use HTTPS if supported
# VAMOSYS_URL = "https://api.vamosys.com/vehicle/tracker/getVehicleData"

# @csrf_exempt
# @require_POST
# def vamosys_proxy(request):
#     """Proxy request from React to Vamosys API"""
#     try:
#         payload = json.loads(request.body.decode("utf-8") or "{}")
#     except json.JSONDecodeError:
#         return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)

#     token = getattr(settings, "VAMOSYS_TOKEN", None)
#     if not token:
#         return JsonResponse(
#             {"status": "error", "message": "Server auth token not configured"},
#             status=500,
#         )

#     try:
#         resp = requests.post(
#             VAMOSYS_URL,
#             json=payload,
#             headers={
#                 "Content-Type": "application/json",
#                 "authenticationtoken": token,
#             },
#             timeout=15,
#         )

#         try:
#             data = resp.json()
#         except ValueError:
#             data = {"raw": resp.text}

#         return JsonResponse(
#             {
#                 "status": "success" if resp.ok else "error",
#                 "upstream_status": resp.status_code,
#                 "data": data,
#             },
#             status=200,
#         )

#     except requests.Timeout:
#         return JsonResponse({"status": "error", "message": "Vamosys API Timeout"}, status=504)
#     except requests.RequestException as e:
#         return JsonResponse({"status": "error", "message": f"Upstream call failed: {str(e)}"}, status=502)
#     except Exception as e:
#         return JsonResponse({"status": "error", "message": f"Internal error: {str(e)}"}, status=500)
