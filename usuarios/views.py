# ============================================================
# USUARIOS/VIEWS.PY / INGRESO Y TOKEN JWT
# El login usa LoginView de Django (sesión + CSRF). El logout es
# LogoutView, que desde Django 5 solo acepta POST: un enlace <a> no
# puede cerrar la sesión de nadie (evita "logout CSRF").
# ============================================================
from django.contrib.auth.views import LoginView
from rest_framework_simplejwt.views import TokenObtainPairView

from .tokens import TokenConRolSerializer


class IngresoView(LoginView):
    template_name = "usuarios/login.html"
    redirect_authenticated_user = True


class TokenConRolView(TokenObtainPairView):
    """POST /api/auth/token/ : usuario y clave -> access + refresh."""

    serializer_class = TokenConRolSerializer
