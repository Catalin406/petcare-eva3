# ============================================================
# URLS.PY / RUTAS RAÍZ DEL PROYECTO
# Cada app registrará aquí sus rutas en su propia fase.
# ============================================================
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
