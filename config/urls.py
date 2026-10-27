# ============================================================
# URLS.PY / RUTAS RAÍZ DEL PROYECTO
# Cada app registra aquí sus rutas en su propia fase.
# ============================================================
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from core.views import InicioView
from usuarios.views import TokenConRolView

urlpatterns = [
    path("", InicioView.as_view(), name="inicio"),
    path("", include("usuarios.urls")),
    path("admin/", admin.site.urls),
    # Autenticación de la API (JWT)
    path("api/auth/token/", TokenConRolView.as_view(), name="token_obtener"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refrescar"),
]

# Páginas de error con el diseño del sitio
handler403 = "core.views.error_403"
handler404 = "core.views.error_404"
handler500 = "core.views.error_500"
