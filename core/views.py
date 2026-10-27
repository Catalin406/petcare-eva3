# ============================================================
# CORE/VIEWS.PY / INICIO Y PÁGINAS DE ERROR
# Las páginas 403/404/500 usan el mismo diseño que el resto del sitio.
# ============================================================
from django.shortcuts import render
from django.views.generic import TemplateView

from .mixins import RolRequeridoMixin


class InicioView(RolRequeridoMixin, TemplateView):
    template_name = "inicio.html"

    def get_context_data(self, **kwargs):
        from .resumen import resumen_para

        contexto = super().get_context_data(**kwargs)
        contexto.update(resumen_para(self.request.user))
        return contexto


def error_403(request, exception=None):
    return render(request, "403.html", {"detalle": str(exception) if exception else ""}, status=403)


def error_404(request, exception=None):
    return render(request, "404.html", status=404)


def error_500(request):
    return render(request, "500.html", status=500)
