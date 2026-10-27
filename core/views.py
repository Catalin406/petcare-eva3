# ============================================================
# CORE/VIEWS.PY / INICIO
# El resumen por rol se completa en la fase de interfaz.
# ============================================================
from django.views.generic import TemplateView

from .mixins import RolRequeridoMixin


class InicioView(RolRequeridoMixin, TemplateView):
    template_name = "inicio.html"
