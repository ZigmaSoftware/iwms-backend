from datetime import timedelta
from django.conf import settings

SIMPLE_JWT = {
    # ONLY Access Token (5 hours)
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=5),

    # Disable refresh tokens
    "REFRESH_TOKEN_LIFETIME": timedelta(seconds=1),  # expires immediately
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,

    "UPDATE_LAST_LOGIN": False,

    "ALGORITHM": "HS256",
    "SIGNING_KEY": settings.SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}
