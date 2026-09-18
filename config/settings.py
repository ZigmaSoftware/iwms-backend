from pathlib import Path
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()
pymysql.install_as_MySQLdb()

BASE_DIR = Path(__file__).resolve().parent.parent
from django.conf import settings

# -------------------------------------------------------
# SECRET KEY – use this one only (your exact key)
# -------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY")

# DEBUG = True

# -------------------------------------------------------
# ENVIRONMENT CONFIG
# -------------------------------------------------------
ENVIRONMENT = os.getenv("DJANGO_ENV", "development")
DEBUG = ENVIRONMENT != "production"


MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    '192.168.1.128',
    '192.168.4.10',
    '.trycloudflare.com',
    '192.168.4.*',
    '192.168.5.*',
    '192.168.5.92',
    "125.17.238.158",
    '10.80.216.123',
    '192.168.4.58',
    '115.245.93.26',
    'testserver',
    '10.64.151.226',
    '10.205.101.232',
    '10.244.208.158',
    '10.183.250.158',  
    '192.168.5.92',
    '192.168.7.176',
    '192.168.5.77',
    '192.168.5.20',
    '192.168.6.198',
    '192.168.1.156',
    '192.168.3.120',
    '10.152.141.197',
    '192.168.3.112',
    '10.255.70.197',
    "aura-haustorial-elayne.ngrok-free.dev",
]

# -------------------------------------------------------
# Installed Apps
# -------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_yasg',

    # Your apps
    'app.apps.ApiConfig',
]

# -------------------------------------------------------
# Middleware
# -------------------------------------------------------
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    'app.middleware.module_permission_middleware.ModulePermissionMiddleware',
    'app.middleware.request_meta_middleware.RequestMetaMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# -------------------------------------------------------
# Database (MySQL)
# -------------------------------------------------------
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'NAME': 'iwmsdb',
#         'USER': 'root',
#         'PASSWORD': 'admin@123',
#         'HOST': 'localhost',
#         'PORT': '3306',
#         'OPTIONS': {
#             'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
#         },
#     }
# }

DATABASES = {   
    'default': {
        'ENGINE': os.getenv("DB_ENGINE", "django.db.backends.mysql"),
        'NAME': os.getenv("DB_NAME", "iwmsdbPrivate"), 
        'USER': os.getenv("DB_USER", "root"),
        'PASSWORD': os.getenv("DB_PASSWORD", "admin@123"),
        'HOST': os.getenv("DB_HOST", "localhost"),
        'PORT': os.getenv("DB_PORT", "3306"),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

SWAGGER_SETTINGS = {
    "USE_SESSION_AUTH": False,

    "SECURITY_DEFINITIONS": {
        "Password": {
            "type": "oauth2",
            "flow": "password",
            "tokenUrl": "/api/v1/login/",
            "scopes": {},
            "description": "Login with username/password to auto-fill the Bearer token.",
        },
    },

    "OAUTH2_CONFIG": {
        "appName": "IWMS API",
    },

    # This is IMPORTANT for your grouped router
    "DEFAULT_AUTO_SCHEMA_CLASS": "app.utils.swagger.GroupedSwaggerAutoSchema",

    "TAGS_SORTER": "alpha",
}

# -------------------------------------------------------
# Password Validators
# -------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# -------------------------------------------------------
# Internationalization
# -------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# -------------------------------------------------------
# Static Files
# -------------------------------------------------------
STATIC_URL = '/static/'
# No project-level `static/` source dir: the only static assets served are the
# ones shipped by django.contrib.admin / DRF / drf-yasg, which collectstatic
# gathers from the installed packages into STATIC_ROOT.
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

ENABLE_AUTH_USER_SEEDING = os.getenv("ENABLE_AUTH_USER_SEEDING", "true").lower() == "true"

# -------------------------------------------------------
# REST Framework
# -------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'app.authentication.jwt.JWTUserAuthentication',
    ],
    # Shared list pagination. Staff-management viewsets explicitly opt out.
    "DEFAULT_PAGINATION_CLASS": "app.utils.pagination.LimitOffsetWithPage",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "app.utils.filters.ModelFieldQueryFilter",
        "app.utils.filters.ModelFieldSearchFilter",
        "app.utils.filters.SerializerOrderingFilter",
    ],
}

# -------------------------------------------------------
# CORS SETTINGS
# -------------------------------------------------------
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://10\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?$",
    r"^http://192\.168\.4\.\d{1,3}(:\d+)?$",
    r"^http://192\.168\.5\.\d{1,3}(:\d+)?$",
    r"^http://192\.168\.1\.\d{1,3}(:\d+)?$",
    r"^http://127\.0\.0\.1(:\d+)?$",
    r"^http://125\.17\.238\.158(:\d+)?$",
    r"^http://localhost(:\d+)?$",
    r"^http://192\.168\.4\.58(:\d+)?$",
    r"^http://192\.168\.5\.92(:\d+)?$",
    r"^http://115\.245\.93\.26(:\d+)?$", 
    r"^http://10\.64\.151\.226(:\d+)?$", #dhivya
    r"^http://10\.205\.101\.232(:\d+)?$", #dhivya
    r"^http://10\.244\.208\.158(:\d+)?$",  
    r"^http://10\.183\.250\.158(:\d+)?$",
    r"^http://192\.168\.7\.176(:\d+)?$",
    r"^http://192\.168\.5\.\.77(:d+)?$",
    r"^http://192\.168\.5\.20(:d+)?$",
    r"^http://192\.168\.6\.198(:d+)?$",
    r"^http://192\.168\.1\.156(:d+)?$",
    r"^http://92\.168\.3\.120(:d+)?$",
    r"^http://10\.152\.141\.197(:d+)?$",
    r"^http://192\.168\.3\.112(:d+)?$",
    r"^http://10\.255\.70\.197(:d+)?$",
    "https://aura-haustorial-elayne.ngrok-free.dev",
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-permission-cache",
    }
}

# -------------------------------------------------------
# Custom User Model
# -------------------------------------------------------
AUTH_USER_MODEL = "app.User"

MY_API_KEY = os.getenv("MY_API_KEY", "abc123")
ORS_API_KEY = os.getenv("ORS_API_KEY", "")
ORS_OPTIMIZATION_URL = os.getenv(
    "ORS_OPTIMIZATION_URL",
    "https://api.openrouteservice.org/optimization",
)
ORS_DIRECTIONS_URL = os.getenv(
    "ORS_DIRECTIONS_URL",
    "https://api.openrouteservice.org/v2/directions/driving-car/geojson",
)

# -------------------------------------------------------
# Email / SMTP
# -------------------------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'true').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@iwms.local')

# OTP settings
OTP_EXPIRY_MINUTES = int(os.getenv('OTP_EXPIRY_MINUTES', 5))
OTP_MAX_ATTEMPTS = int(os.getenv('OTP_MAX_ATTEMPTS', 3))
OTP_RESEND_COOLDOWN_MINUTES = int(os.getenv('OTP_RESEND_COOLDOWN_MINUTES', 2))
OTP_MAX_REQUESTS_PER_WINDOW = int(os.getenv('OTP_MAX_REQUESTS_PER_WINDOW', 3))
OTP_RATE_WINDOW_MINUTES = int(os.getenv('OTP_RATE_WINDOW_MINUTES', 10))

# -------------------------------------------------------
# PUSH NOTIFICATIONS (Firebase Cloud Messaging)
# -------------------------------------------------------
# See app/services/push_notification_service.py — self-gating: sending is a
# safe no-op until this points at a real service-account JSON. Deliberately a
# SEPARATE Firebase project from iwms-government-backend's — private and
# government are distinct products for distinct customers and must never
# share delivery credentials, quota, or Android app registration.
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "")

# -------------------------------------------------------
# ATTENDANCE FACE RECOGNITION
# -------------------------------------------------------
# Which engine verifies attendance selfies. Both are fully supported; this is
# the only line that has to change to switch, plus a server restart. The
# register/recognise HTTP contract is identical either way, so the mobile app
# needs no rebuild — it can read the active provider from
# `GET attendance/face-config/`.
#
#   compreface  — the hosted CompreFace API (unchanged, long-standing default)
#   insightface — recognition running inside this server, no external API
#
# Left unset it stays on CompreFace, so deploying this change on its own does
# not silently move anyone onto a different engine.
FACE_RECOGNITION_PROVIDER = os.getenv("FACE_RECOGNITION_PROVIDER", "compreface")

# --- CompreFace (hosted API) ---
# These were hardcoded in the attendance viewsets; they live here now so the
# host can be repointed and the key rotated without a code change.
COMPREFACE_VERIFY_URL = os.getenv(
    "COMPREFACE_VERIFY_URL",
    "http://125.17.238.158:8000/api/v1/verification/verify",
)
COMPREFACE_API_KEY = os.getenv(
    "COMPREFACE_API_KEY", "c4bb2855-e789-45e4-8dcd-903f03e03f2f"
)
COMPREFACE_TIMEOUT = int(os.getenv("COMPREFACE_TIMEOUT", "30"))
# CompreFace's own 0-1 confidence. NOT comparable to the cosine similarity
# InsightFace reports below — each provider carries its own cutoff.
COMPREFACE_MATCH_THRESHOLD = float(os.getenv("COMPREFACE_MATCH_THRESHOLD", "0.95"))

# --- InsightFace (in-process) ---
# Model pack, auto-downloaded to FACE_MODEL_ROOT (~/.insightface) on first
# use. buffalo_s is small and fast; buffalo_l is more accurate but a larger
# download and slower on CPU.
FACE_MODEL_NAME = os.getenv("FACE_MODEL_NAME", "buffalo_s")
FACE_MODEL_ROOT = os.getenv("FACE_MODEL_ROOT", "")
FACE_DET_SIZE = int(os.getenv("FACE_DET_SIZE", "640"))
# Cosine similarity between normalised ArcFace embeddings: genuine matches sit
# around 0.45-0.75, different people around 0.0-0.25. Tune against real punch
# photos before trusting it — and never reuse CompreFace's 0.95 here, which
# would reject every genuine employee.
FACE_MATCH_THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.5"))
# Caps the CPU threads one inference may take, so a shift-start burst of
# punches cannot starve the rest of the API on a shared server.
FACE_ONNX_THREADS = int(os.getenv("FACE_ONNX_THREADS", "2"))
FACE_MAX_IMAGE_EDGE = int(os.getenv("FACE_MAX_IMAGE_EDGE", "1280"))
FACE_MIN_DET_SCORE = float(os.getenv("FACE_MIN_DET_SCORE", "0.5"))
FACE_MIN_PIXELS = int(os.getenv("FACE_MIN_PIXELS", "60"))
# Laplacian-variance blur gate. A quality check, not anti-spoofing — a sharp
# photo of a photo passes it. 0 disables.
FACE_MIN_SHARPNESS = float(os.getenv("FACE_MIN_SHARPNESS", "0"))

# -------------------------------------------------------
# JWT CONFIG (import at the end)
# -------------------------------------------------------
from .settings_jwt import *
