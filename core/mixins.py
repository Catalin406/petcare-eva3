# ============================================================
# CORE/MIXINS.PY / PERMISOS POR ROL PARA VISTAS HTML
# Una sola clase base para declarar qué roles entran a cada vista.
# Anónimo -> redirige al login; autenticado sin rol permitido -> 403
# (página propia con el mismo diseño).
# ============================================================
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class RolRequeridoMixin(LoginRequiredMixin):
    roles_permitidos = ()  # cada vista lo redefine; vacío = cualquier rol autenticado

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and self.roles_permitidos:
            if request.user.rol not in self.roles_permitidos:
                raise PermissionDenied("Tu rol no tiene acceso a esta sección.")
        return super().dispatch(request, *args, **kwargs)
