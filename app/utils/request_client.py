"""Which client a request came from — used by the App Module login gate.

The app sends `client: "mobile"` on every login (see AuthRepository in the
Flutter app); a browser sends nothing, which defaults to "web".
"""

MOBILE_CLIENT_VALUES = {"mobile", "app", "android", "ios"}


def is_mobile_client(data):
    value = str((data or {}).get("client") or "web").strip().lower()
    return value in MOBILE_CLIENT_VALUES
