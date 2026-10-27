# ============================================================
# SETTINGS.PY / CONFIGURACIÓN CENTRAL DE PETCARE
# Apps, PostgreSQL, sesiones, seguridad, DRF/JWT y localización
# chilena. Todo dato sensible o dependiente del entorno se lee de
# .env con python-decouple: nunca se escribe en el código.
# ============================================================
from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================
# SEGURIDAD BÁSICA
# SECRET_KEY no tiene valor por defecto: si falta en .env, el
# proyecto no arranca (mejor fallar que correr con una clave débil).
# ============================================================
SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

# ============================================================
# DESPLIEGUE DETRÁS DE NGINX CON HTTPS
# Nginx termina el HTTPS y avisa con X-Forwarded-Proto (vía
# "include proxy_params"). DETRAS_DE_PROXY_HTTPS=True se activa SOLO
# en el servidor: Django cree ese encabezado, redirige a https y
# marca las cookies como seguras. HSTS parte bajo (1 hora, sin
# preload) para poder corregir errores de HTTPS sin bloquear el sitio.
# CSRF_TRUSTED_ORIGINS: orígenes https aceptados en los POST.
# ============================================================
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())
DETRAS_DE_PROXY_HTTPS = config("DETRAS_DE_PROXY_HTTPS", default=False, cast=bool)
# Las cookies seguras se pueden activar solas (p. ej. HTTPS directo)
# o junto con el proxy; por defecto siguen a DETRAS_DE_PROXY_HTTPS.
COOKIES_SEGURAS = config("COOKIES_SEGURAS", default=DETRAS_DE_PROXY_HTTPS, cast=bool)
SESSION_COOKIE_SECURE = COOKIES_SEGURAS
CSRF_COOKIE_SECURE = COOKIES_SEGURAS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
if DETRAS_DE_PROXY_HTTPS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = config("HSTS_SEGUNDOS", default=3600, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False
# W021 pide HSTS preload (1 año, irreversible en los navegadores):
# se descarta a propósito en un sitio de evaluación.
SILENCED_SYSTEM_CHECKS = ["security.W021"]

# ============================================================
# SESIONES
# La sesión expira por inactividad: cada petición renueva el plazo.
# Datos clínicos: una sesión olvidada no debe quedar abierta horas.
# ============================================================
SESSION_COOKIE_AGE = config("SESSION_EXPIRA_SEGUNDOS", default=1800, cast=int)
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# ============================================================
# DATOS DEL ESTUDIANTE Y MARCA
# Se muestran en el footer (context processor) y en Swagger.
# ============================================================
ALUMNO_NOMBRE = config("ALUMNO_NOMBRE", default="Catalina Quezada Sanzana")
ALUMNO_SECCION = config("ALUMNO_SECCION", default="")
ALUMNO_ANIO = config("ALUMNO_ANIO", default="2026")
NOMBRE_COMERCIAL = "PetCare"

# ============================================================
# REGLAS DE NEGOCIO CONFIGURABLES
# ============================================================
# Horas mínimas de anticipación para que un TUTOR pida o cancele una cita.
CITA_ANTICIPACION_MIN_HORAS = config("CITA_ANTICIPACION_MIN_HORAS", default=24, cast=int)
# Ventana (días) que revisa el comando generar_recordatorios.
DIAS_ANTICIPACION_RECORDATORIO = config("DIAS_ANTICIPACION_RECORDATORIO", default=30, cast=int)

# ============================================================
# APLICACIONES INSTALADAS
# django.contrib.postgres es necesario para ExclusionConstraint y
# BtreeGistExtension (anti-solapamiento de citas en la base de datos).
# ============================================================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # Terceros
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "drf_spectacular",
    # Propias (se suman por fase)
    "core",
    "usuarios.apps.UsuariosConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.LoginRequeridoMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# ============================================================
# PLANTILLAS
# ============================================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.datos_alumno",
            ],
        },
    },
]

# ============================================================
# BASE DE DATOS: SOLO POSTGRESQL (driver psycopg 3)
# Sin valores por defecto para nombre, usuario y clave: si faltan,
# el proyecto avisa en vez de conectarse a una base equivocada.
# ============================================================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
    }
}

# ============================================================
# USUARIO PERSONALIZADO Y RUTAS DE AUTENTICACIÓN
# ============================================================
AUTH_USER_MODEL = "usuarios.Usuario"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "inicio"
LOGOUT_REDIRECT_URL = "login"

# ============================================================
# VALIDADORES DE CONTRASEÑA
# ============================================================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ============================================================
# LOCALIZACIÓN (CHILE)
# ============================================================
LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

# ============================================================
# ARCHIVOS ESTÁTICOS Y ARCHIVOS PRIVADOS
# Los estáticos (CSS/JS) son públicos. Las fotos de mascotas y los
# adjuntos de exámenes son datos clínicos: NO hay MEDIA_URL ni se
# sirven desde /media/. Se guardan en ARCHIVOS_PRIVADOS_ROOT (fuera
# de static) y solo una vista con login y permisos los entrega.
# ============================================================
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
ARCHIVOS_PRIVADOS_ROOT = BASE_DIR / "archivos_privados"
ARCHIVO_MAX_MB = 5

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ============================================================
# CORREO
# Por defecto imprime en consola (sin servidor SMTP). El comando
# generar_recordatorios envía por aquí.
# ============================================================
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = config("EMAIL_DESDE", default="PetCare <no-responder@petcare.local>")

# ============================================================
# MENSAJES FLASH → clases de alerta de Bootstrap
# ============================================================
from django.contrib.messages import constants as mensajes  # noqa: E402

MESSAGE_TAGS = {mensajes.ERROR: "danger"}

# ============================================================
# DJANGO REST FRAMEWORK
# JWT + sesión; todo exige autenticación (datos clínicos).
# ============================================================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# Access corto (30 min) y refresh de 1 día.
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "TOKEN_OBTAIN_SERIALIZER": "usuarios.tokens.TokenConRolSerializer",
}
