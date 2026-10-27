# ============================================================
# CORE/MIDDLEWARE.PY / LOGIN OBLIGATORIO EN TODA LA APLICACIÓN WEB
# Hay datos clínicos: ninguna página es pública. Este middleware es la
# red de seguridad global; además cada vista declara su rol con
# RolRequeridoMixin. Si una vista futura olvidara el mixin, igual
# quedaría protegida aquí.
# Excepciones: la pantalla de login, los estáticos, el Admin (tiene su
# propio login) y /api/ (responde 401 JSON en vez de redirigir).
# ============================================================
from django.conf import settings
from django.shortcuts import redirect, resolve_url
from django.utils.http import urlencode


class LoginRequeridoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated and not self._es_publica(request.path):
            destino = resolve_url(settings.LOGIN_URL)
            return redirect(f"{destino}?{urlencode({'next': request.get_full_path()})}")
        return self.get_response(request)

    @staticmethod
    def _es_publica(ruta):
        prefijos_libres = (
            resolve_url(settings.LOGIN_URL),
            "/" + settings.STATIC_URL.lstrip("/"),
            "/admin/",
            "/api/",
        )
        return ruta.startswith(prefijos_libres)
