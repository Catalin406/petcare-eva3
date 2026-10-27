# ============================================================
# VACUNACION/VIEWS.PY / VISTAS WEB DE RECORDATORIOS, VACUNAS Y CONTROLES
# Panel de recordatorios: todos los roles (el tutor ve solo los suyos).
# Catálogo de vacunas: lo edita administrador/veterinario.
# Aplicación de vacunas: veterinario y administrador.
# Controles: recepción, veterinario y administrador.
# ============================================================
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, FormView, ListView, TemplateView, UpdateView

from core.mixins import FormularioSimpleMixin, PaginacionConFiltrosMixin, RolRequeridoMixin
from usuarios.models import Rol

from . import servicios
from .forms import ControlForm, RegistroVacunaForm, VacunaForm
from .models import Vacuna

VETERINARIA = (Rol.ADMINISTRADOR, Rol.VETERINARIO)
GESTION = (Rol.ADMINISTRADOR, Rol.VETERINARIO, Rol.RECEPCIONISTA)


class RecordatorioPanelView(RolRequeridoMixin, TemplateView):
    template_name = "vacunacion/recordatorios.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(**servicios.panel_recordatorios(self.request.user), **kwargs)


# ---------------- Catálogo de vacunas ----------------
class VacunaListaView(RolRequeridoMixin, ListView):
    roles_permitidos = GESTION
    template_name = "vacunacion/vacuna_lista.html"
    context_object_name = "vacunas"
    queryset = Vacuna.objects.all()

    def get_context_data(self, **kwargs):
        return super().get_context_data(puede_editar=self.request.user.rol in VETERINARIA, **kwargs)


class VacunaCrearView(RolRequeridoMixin, FormularioSimpleMixin, CreateView):
    roles_permitidos = VETERINARIA
    form_class = VacunaForm
    titulo = "Nueva vacuna del catálogo"
    mensaje_exito = "Vacuna agregada al catálogo."
    nombre_url_volver = "vacuna_lista"
    success_url = reverse_lazy("vacuna_lista")


class VacunaEditarView(RolRequeridoMixin, FormularioSimpleMixin, UpdateView):
    roles_permitidos = VETERINARIA
    model = Vacuna
    form_class = VacunaForm
    titulo = "Editar vacuna"
    mensaje_exito = "Vacuna actualizada."
    nombre_url_volver = "vacuna_lista"
    success_url = reverse_lazy("vacuna_lista")


class VacunaEliminarView(RolRequeridoMixin, View):
    """Una vacuna ya aplicada no se borra del catálogo: se desactiva."""

    roles_permitidos = VETERINARIA

    def get(self, request, pk):
        vacuna = get_object_or_404(Vacuna, pk=pk)
        usada = vacuna.registros.exists()
        return render(request, "crud/confirmar_eliminar.html", {
            "titulo_pagina": f"Eliminar vacuna: {vacuna.nombre}",
            "mensaje_confirmacion": "Ya fue aplicada a mascotas, por eso solo se desactivará." if usada else "Se eliminará del catálogo.",
            "texto_boton": "Desactivar" if usada else "Eliminar", "url_volver": reverse("vacuna_lista"),
        })

    def post(self, request, pk):
        vacuna = get_object_or_404(Vacuna, pk=pk)
        if vacuna.registros.exists():
            vacuna.activa = False
            vacuna.save(update_fields=["activa"])
            messages.success(request, f"{vacuna.nombre} quedó desactivada.")
        else:
            vacuna.delete()
            messages.success(request, "Vacuna eliminada del catálogo.")
        return redirect("vacuna_lista")


# ---------------- Aplicaciones de vacunas ----------------
class RegistroVacunaListaView(RolRequeridoMixin, PaginacionConFiltrosMixin, ListView):
    template_name = "vacunacion/registro_lista.html"
    context_object_name = "registros"

    def get_queryset(self):
        consulta = servicios.registros_vacuna_visibles(self.request.user)
        q = self.request.GET.get("q", "").strip()
        if q:
            consulta = consulta.filter(Q(mascota__nombre__icontains=q) | Q(vacuna__nombre__icontains=q))
        return consulta.order_by("proxima_dosis")

    def get_context_data(self, **kwargs):
        return super().get_context_data(puede_registrar=self.request.user.rol in VETERINARIA, **kwargs)


class RegistroVacunaCrearView(RolRequeridoMixin, FormularioSimpleMixin, FormView):
    roles_permitidos = VETERINARIA
    form_class = RegistroVacunaForm
    titulo = "Registrar vacuna aplicada"
    nombre_url_volver = "registro_vacuna_lista"

    def get_initial(self):
        return {"mascota": self.request.GET["mascota"]} if self.request.GET.get("mascota") else {}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario"] = self.request.user
        return kwargs

    def form_valid(self, form):
        registro = form.guardar()
        if registro is None:
            return self.render_to_response(self.get_context_data(form=form))
        messages.success(
            self.request,
            f"Vacuna registrada. Próxima dosis de {registro.vacuna.nombre}: {registro.proxima_dosis:%d/%m/%Y}.",
        )
        return redirect("registro_vacuna_lista")


# ---------------- Controles periódicos ----------------
class ControlListaView(RolRequeridoMixin, PaginacionConFiltrosMixin, ListView):
    template_name = "vacunacion/control_lista.html"
    context_object_name = "controles"

    def get_queryset(self):
        return servicios.controles_visibles(self.request.user).order_by("realizado", "fecha_programada")

    def get_context_data(self, **kwargs):
        return super().get_context_data(puede_gestionar=self.request.user.rol in GESTION, **kwargs)


class ControlFormularioMixin(RolRequeridoMixin, FormularioSimpleMixin):
    roles_permitidos = GESTION
    form_class = ControlForm
    nombre_url_volver = "control_lista"
    success_url = reverse_lazy("control_lista")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario"] = self.request.user
        return kwargs


class ControlCrearView(ControlFormularioMixin, CreateView):
    titulo = "Programar control periódico"
    mensaje_exito = "Control programado."


class ControlEditarView(ControlFormularioMixin, UpdateView):
    titulo = "Editar control periódico"
    mensaje_exito = "Control actualizado."

    def get_queryset(self):
        return servicios.controles_visibles(self.request.user)


class ControlRealizadoView(RolRequeridoMixin, View):
    roles_permitidos = GESTION

    def post(self, request, pk):
        control = get_object_or_404(servicios.controles_visibles(request.user), pk=pk)
        servicios.marcar_control_realizado(control)
        messages.success(request, "Control marcado como realizado.")
        return redirect("control_lista")
