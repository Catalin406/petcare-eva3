# ============================================================
# CLIENTES/VIEWS.PY / VISTAS WEB DE TUTORES Y MASCOTAS
# Las vistas solo orquestan: validan permisos, llaman a los servicios
# y muestran mensajes. Un tutor solo llega a SUS mascotas porque todo
# parte de mascotas_visibles(): lo ajeno responde 404.
# ============================================================
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from core.archivos import entregar_archivo
from core.mixins import PaginacionConFiltrosMixin, RolRequeridoMixin
from usuarios.models import Rol

from . import servicios
from .forms import MascotaForm, TutorForm
from .models import Especie, Mascota, Tutor

STAFF = (Rol.ADMINISTRADOR, Rol.RECEPCIONISTA)
TODOS = (Rol.ADMINISTRADOR, Rol.RECEPCIONISTA, Rol.VETERINARIO, Rol.TUTOR)


# ------------------------------------------------------------
# TUTORES (solo administrador y recepción)
# ------------------------------------------------------------
class TutorListaView(RolRequeridoMixin, PaginacionConFiltrosMixin, ListView):
    roles_permitidos = STAFF
    template_name = "clientes/tutor_lista.html"
    context_object_name = "tutores"

    def get_queryset(self):
        consulta = servicios.tutores_visibles(self.request.user).prefetch_related("mascotas")
        q = self.request.GET.get("q", "").strip()
        if q:
            consulta = consulta.filter(
                Q(rut__icontains=q) | Q(usuario__first_name__icontains=q)
                | Q(usuario__last_name__icontains=q) | Q(usuario__email__icontains=q)
            )
        return consulta


class TutorDetalleView(RolRequeridoMixin, DetailView):
    roles_permitidos = STAFF
    template_name = "clientes/tutor_detalle.html"
    context_object_name = "tutor"

    def get_queryset(self):
        return servicios.tutores_visibles(self.request.user).prefetch_related("mascotas")


class TutorFormularioMixin(RolRequeridoMixin):
    roles_permitidos = STAFF
    template_name = "crud/formulario.html"
    form_class = TutorForm

    def form_valid(self, form):
        tutor = form.guardar()
        if tutor is None:
            return self.form_invalid(form)
        messages.success(self.request, self.mensaje_exito.format(tutor=tutor.nombre_completo))
        return redirect("tutor_detalle", pk=tutor.pk)


class TutorCrearView(TutorFormularioMixin, FormView):
    mensaje_exito = "Tutor {tutor} creado correctamente."

    def get_context_data(self, **kwargs):
        return super().get_context_data(titulo_pagina="Nuevo tutor", url_volver=reverse("tutor_lista"), **kwargs)


class TutorEditarView(TutorFormularioMixin, FormView):
    mensaje_exito = "Datos de {tutor} actualizados."

    @cached_property
    def tutor(self):
        return get_object_or_404(servicios.tutores_visibles(self.request.user), pk=self.kwargs["pk"])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.tutor
        return kwargs

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            titulo_pagina=f"Editar tutor: {self.tutor.nombre_completo}",
            url_volver=reverse("tutor_detalle", args=[self.tutor.pk]), **kwargs,
        )


class TutorEliminarView(RolRequeridoMixin, View):
    """GET muestra la confirmación; POST decide entre eliminar o desactivar."""

    roles_permitidos = STAFF

    def get(self, request, pk):
        from django.shortcuts import render

        tutor = get_object_or_404(servicios.tutores_visibles(request.user), pk=pk)
        con_mascotas = tutor.mascotas.exists()
        return render(request, "crud/confirmar_eliminar.html", {
            "titulo_pagina": f"Eliminar tutor: {tutor.nombre_completo}",
            "mensaje_confirmacion": (
                "Este tutor tiene mascotas, por eso NO se borrará: su cuenta quedará desactivada y las fichas se conservan."
                if con_mascotas else "Se eliminará el tutor y su cuenta. Esta acción no se puede deshacer."
            ),
            "texto_boton": "Desactivar" if con_mascotas else "Eliminar",
            "url_volver": reverse("tutor_detalle", args=[pk]),
        })

    def post(self, request, pk):
        tutor = get_object_or_404(servicios.tutores_visibles(request.user), pk=pk)
        nombre = tutor.nombre_completo
        resultado = servicios.eliminar_o_desactivar_tutor(tutor)
        messages.success(request, f"Tutor {nombre} {resultado}.")
        return redirect("tutor_lista")


# ------------------------------------------------------------
# MASCOTAS
# Lectura: todos los roles (el tutor, solo las suyas).
# Alta/edición/baja: administrador y recepción.
# ------------------------------------------------------------
class MascotaListaView(RolRequeridoMixin, PaginacionConFiltrosMixin, ListView):
    template_name = "clientes/mascota_lista.html"
    context_object_name = "mascotas"

    def get_queryset(self):
        consulta = servicios.mascotas_visibles(self.request.user)
        q = self.request.GET.get("q", "").strip()
        especie = self.request.GET.get("especie", "")
        estado = self.request.GET.get("estado", "")
        if q:
            consulta = consulta.filter(
                Q(nombre__icontains=q) | Q(microchip__icontains=q) | Q(raza__icontains=q)
                | Q(tutor__rut__icontains=q) | Q(tutor__usuario__last_name__icontains=q)
            )
        if especie:
            consulta = consulta.filter(especie=especie)
        if estado == "activas":
            consulta = consulta.filter(activa=True)
        elif estado == "inactivas":
            consulta = consulta.filter(activa=False)
        return consulta

    def get_context_data(self, **kwargs):
        return super().get_context_data(especies=Especie.choices, **kwargs)


class MascotaDetalleView(RolRequeridoMixin, DetailView):
    template_name = "clientes/mascota_detalle.html"
    context_object_name = "mascota"

    def get_queryset(self):
        return servicios.mascotas_visibles(self.request.user)

    def get_context_data(self, **kwargs):
        from core.resumen import contexto_mascota

        contexto = super().get_context_data(**kwargs)
        contexto.update(contexto_mascota(self.request.user, self.object))
        return contexto


class MascotaCrearView(RolRequeridoMixin, CreateView):
    roles_permitidos = STAFF
    model = Mascota
    form_class = MascotaForm
    template_name = "crud/formulario.html"

    def get_initial(self):
        inicial = super().get_initial()
        if self.request.GET.get("tutor"):
            inicial["tutor"] = self.request.GET["tutor"]
        return inicial

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Mascota {self.object.nombre} registrada. Su ficha clínica se creó automáticamente.")
        return respuesta

    def get_success_url(self):
        return reverse("mascota_detalle", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        return super().get_context_data(titulo_pagina="Nueva mascota", url_volver=reverse("mascota_lista"), **kwargs)


class MascotaEditarView(RolRequeridoMixin, UpdateView):
    roles_permitidos = STAFF
    form_class = MascotaForm
    template_name = "crud/formulario.html"

    def get_queryset(self):
        return servicios.mascotas_visibles(self.request.user)

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Datos de {self.object.nombre} actualizados.")
        return respuesta

    def get_success_url(self):
        return reverse("mascota_detalle", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            titulo_pagina=f"Editar mascota: {self.object.nombre}",
            url_volver=reverse("mascota_detalle", args=[self.object.pk]), **kwargs,
        )


class MascotaEliminarView(RolRequeridoMixin, View):
    roles_permitidos = STAFF

    def get(self, request, pk):
        from django.shortcuts import render

        mascota = get_object_or_404(servicios.mascotas_visibles(request.user), pk=pk)
        historial = servicios.tiene_historial_clinico(mascota)
        return render(request, "crud/confirmar_eliminar.html", {
            "titulo_pagina": f"Eliminar mascota: {mascota.nombre}",
            "mensaje_confirmacion": (
                "Tiene historial clínico, por eso NO se borrará: quedará desactivada y su ficha se conserva."
                if historial else "No tiene historial: se eliminará junto con su ficha vacía."
            ),
            "texto_boton": "Desactivar" if historial else "Eliminar",
            "url_volver": reverse("mascota_detalle", args=[pk]),
        })

    def post(self, request, pk):
        mascota = get_object_or_404(servicios.mascotas_visibles(request.user), pk=pk)
        nombre = mascota.nombre
        resultado = servicios.eliminar_o_desactivar_mascota(mascota)
        messages.success(request, f"Mascota {nombre} {resultado}.")
        return redirect("mascota_lista")


class MascotaFotoView(RolRequeridoMixin, View):
    """Entrega la foto solo a quien puede ver la mascota (nunca desde /media/)."""

    def get(self, request, pk):
        mascota = get_object_or_404(servicios.mascotas_visibles(request.user), pk=pk)
        return entregar_archivo(mascota.foto)
