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


class FormularioSimpleMixin:
    """
    Alta/edición con la plantilla genérica crud/formulario.html.
    La vista define: titulo, mensaje_exito, nombre_url_volver (y get_success_url).
    """

    template_name = "crud/formulario.html"
    titulo = ""
    mensaje_exito = "Los cambios se guardaron."
    nombre_url_volver = None

    def get_context_data(self, **kwargs):
        from django.urls import reverse

        contexto = super().get_context_data(**kwargs)
        contexto["titulo_pagina"] = self.titulo
        if self.nombre_url_volver:
            contexto["url_volver"] = reverse(self.nombre_url_volver)
        return contexto

    def form_valid(self, form):
        from django.contrib import messages

        respuesta = super().form_valid(form)
        messages.success(self.request, self.mensaje_exito)
        return respuesta
