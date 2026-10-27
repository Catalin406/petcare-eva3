# ============================================================
# URLS.PY / RUTAS RAÍZ DEL PROYECTO
# Web (HTML) en la raíz, API REST bajo /api/, documentación Swagger
# en /api/docs/ y Django Admin en /admin/.
# ============================================================
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

from core.views import InicioView
from usuarios.views import TokenConRolView

urlpatterns = [
    path("", InicioView.as_view(), name="inicio"),
    path("", include("usuarios.urls")),
    path("", include("clientes.urls")),
    path("", include("agenda.urls")),
    path("", include("clinica.urls")),
    path("", include("vacunacion.urls")),
    path("admin/", admin.site.urls),
    # API REST
    path("api/auth/token/", TokenConRolView.as_view(), name="token_obtener"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refrescar"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
    path("api/", include("config.api_urls")),
]

# Páginas de error con el diseño del sitio
handler403 = "core.views.error_403"
handler404 = "core.views.error_404"
handler500 = "core.views.error_500"
