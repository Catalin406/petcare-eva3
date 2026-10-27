# ============================================================
# ASGI.PY / PUNTO DE ENTRADA ASGI
# Punto de entrada ASGI (el despliegue usa WSGI con Gunicorn).
# ============================================================
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_asgi_application()
