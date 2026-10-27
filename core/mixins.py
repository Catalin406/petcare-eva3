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


class PaginacionConFiltrosMixin:
    """Conserva los filtros (?q=...) al cambiar de página en los listados."""

    paginate_by = 12

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        parametros = self.request.GET.copy()
        parametros.pop("page", None)
        contexto["consulta_sin_pagina"] = parametros.urlencode() + "&" if parametros else ""
        return contexto
