import os
from datetime import timedelta

SIMPLE_JWT = {
    # ONLY Access Token (5 hours)
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=5),

    # Disable refresh tokens
    "REFRESH_TOKEN_LIFETIME": timedelta(seconds=1),  # expires immediately
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,

    "UPDATE_LAST_LOGIN": False,

    "ALGORITHM": "HS256",
    "SIGNING_KEY": os.getenv("SECRET_KEY", ""),
    "AUTH_HEADER_TYPES": ("Bearer",),
    # Use pk so tokens can be minted for both Staffcreation and User
    # (their primary keys differ, but pk always resolves correctly).
    "USER_ID_FIELD": "pk",
}

# Web sessions are auto-logged-out after this many minutes with no user
# activity (mouse / keyboard / touch). The value is sent to the browser in the
# login response and also enforced server-side on every authenticated request.
LOGIN_IDLE_TIMEOUT_SECONDS = int(os.getenv("LOGIN_IDLE_TIMEOUT_MINUTES", "40")) * 60

# Web portals keep their access token in an HttpOnly cookie (see
# app/authentication/cookies.py). Set AUTH_COOKIE_SECURE=true once the site
# is served over HTTPS; browsers drop Secure cookies on plain HTTP.
AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"
AUTH_COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "Lax")
AUTH_COOKIE_DOMAIN = os.getenv("AUTH_COOKIE_DOMAIN") or None
