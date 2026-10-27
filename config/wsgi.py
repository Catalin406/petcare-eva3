# ============================================================
# WSGI.PY / PUNTO DE ENTRADA WSGI
# Gunicorn carga "config.wsgi:application" en el servidor.
# ============================================================
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()
