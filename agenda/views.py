# ============================================================
# AGENDA/VIEWS.PY / VISTAS WEB DE CALENDARIO, CITAS, DISPONIBILIDAD Y BLOQUEOS
# Roles:
#   Citas       -> ADMIN y RECEPCIÓN gestionan; VETERINARIO ve y confirma su agenda;
#                  TUTOR ve las suyas, solicita y cancela.
#   Disponib.   -> VETERINARIO (la propia) y ADMIN.
# ============================================================
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import DetailView, FormView, ListView, TemplateView

from core.mixins import PaginacionConFiltrosMixin, RolRequeridoMixin
from usuarios.models import Rol

from . import servicios
from .forms import BloqueoForm, CitaForm, DisponibilidadForm
from .models import BloqueoAgenda, Cita, DisponibilidadSemanal, EstadoCita, Profesional

STAFF = (Rol.ADMINISTRADOR, Rol.RECEPCIONISTA)
AGENDA_PROPIA = (Rol.ADMINISTRADOR, Rol.VETERINARIO)


def _profesional_de(usuario):
    """Profesional ligado al usuario veterinario (None si no es veterinario)."""
    return Profesional.objects.filter(usuario=usuario).first() if usuario.rol == Rol.VETERINARIO else None


# ------------------------------------------------------------
# CALENDARIO (FullCalendar consume la API por fetch)
# ------------------------------------------------------------
class CalendarioView(RolRequeridoMixin, TemplateView):
    template_name = "agenda/calendario.html"

    def get_context_data(self, **kwargs):
        profesionales = Profesional.objects.select_related("usuario").filter(activo=True, usuario__is_active=True)
        propio = _profesional_de(self.request.user)
        if propio is not None:
            profesionales = profesionales.filter(pk=propio.pk)
        elegido = self.request.GET.get("profesional")
        return super().get_context_data(
            profesionales=profesionales,
            profesional_inicial=elegido if elegido else (profesionales.first().pk if profesionales.exists() else ""),
            puede_agendar=self.request.user.rol in (Rol.ADMINISTRADOR, Rol.RECEPCIONISTA, Rol.TUTOR),
            **kwargs,
        )


# ------------------------------------------------------------
# CITAS
# ------------------------------------------------------------
class CitaListaView(RolRequeridoMixin, PaginacionConFiltrosMixin, ListView):
    template_name = "agenda/cita_lista.html"
    context_object_name = "citas"

    def get_queryset(self):
        consulta = servicios.citas_visibles(self.request.user)
        q = self.request.GET.get("q", "").strip()
        estado = self.request.GET.get("estado", "")
        periodo = self.request.GET.get("periodo", "proximas")
        profesional = self.request.GET.get("profesional", "")
        if q:
            consulta = consulta.filter(Q(mascota__nombre__icontains=q) | Q(motivo__icontains=q))
        if estado in EstadoCita.values:
            consulta = consulta.filter(estado=estado)
        if profesional.isdigit():
            consulta = consulta.filter(profesional_id=profesional)
        ahora = timezone.now()
        if periodo == "proximas":
            consulta = consulta.filter(fin__gte=ahora).order_by("inicio")
        elif periodo == "pasadas":
            consulta = consulta.filter(fin__lt=ahora).order_by("-inicio")
        return consulta

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            estados=EstadoCita.choices,
            profesionales=Profesional.objects.select_related("usuario").filter(activo=True),
            puede_agendar=self.request.user.rol in (Rol.ADMINISTRADOR, Rol.RECEPCIONISTA, Rol.TUTOR),
            **kwargs,
        )


class CitaDetalleView(RolRequeridoMixin, DetailView):
    template_name = "agenda/cita_detalle.html"
    context_object_name = "cita"

    def get_queryset(self):
        return servicios.citas_visibles(self.request.user).prefetch_related("historial__usuario")

    def get_context_data(self, **kwargs):
        cita, usuario = self.object, self.request.user
        activa = cita.estado in (EstadoCita.PROGRAMADA, EstadoCita.CONFIRMADA)
        propia_vet = usuario.rol == Rol.VETERINARIO and cita.profesional.usuario_id == usuario.pk
        return super().get_context_data(
            puede_cancelar=activa and usuario.rol in (*STAFF, Rol.TUTOR),
            puede_confirmar=cita.estado == EstadoCita.PROGRAMADA and (usuario.rol in STAFF or propia_vet),
            puede_no_asistio=activa and cita.inicio <= timezone.now() and (usuario.rol in STAFF or propia_vet),
            puede_atender=activa and propia_vet,
            puede_reprogramar=activa and usuario.rol in STAFF,
            puede_eliminar=usuario.rol == Rol.ADMINISTRADOR,
            tiene_atencion=hasattr(cita, "atencion"),
            **kwargs,
        )


class CitaFormularioMixin(RolRequeridoMixin, FormView):
    template_name = "agenda/cita_form.html"
    form_class = CitaForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario"] = self.request.user
        return kwargs

    def form_valid(self, form):
        cita = form.guardar()
        if cita is None:
            return form_invalido(self, form)
        messages.success(self.request, self.mensaje_exito)
        return redirect("cita_detalle", pk=cita.pk)


def form_invalido(vista, form):
    return vista.render_to_response(vista.get_context_data(form=form))


class CitaCrearView(CitaFormularioMixin):
    roles_permitidos = (*STAFF, Rol.TUTOR)
    mensaje_exito = "Cita agendada correctamente."

    def get_initial(self):
        inicial = {}
        for campo in ("mascota", "profesional"):
            if self.request.GET.get(campo):
                inicial[campo] = self.request.GET[campo]
        # El calendario envía ?inicio=2026-11-03T10:00 al hacer clic en un bloque libre.
        if self.request.GET.get("inicio"):
            try:
                inicio = timezone.localtime(datetime.fromisoformat(self.request.GET["inicio"]).astimezone()) \
                    if "+" in self.request.GET["inicio"] else datetime.fromisoformat(self.request.GET["inicio"])
                inicial["fecha"], inicial["hora"] = inicio.date(), inicio.strftime("%H:%M")
            except ValueError:
                pass
        return inicial

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            titulo_pagina="Agendar cita", url_volver=reverse("cita_lista"),
            anticipacion=settings.CITA_ANTICIPACION_MIN_HORAS,
            **kwargs,
        )


class CitaEditarView(CitaFormularioMixin):
    roles_permitidos = STAFF
    mensaje_exito = "Cita reprogramada correctamente."

    @cached_property
    def cita(self):
        return get_object_or_404(servicios.citas_visibles(self.request.user), pk=self.kwargs["pk"])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["cita"] = self.cita
        return kwargs

    def get_initial(self):
        local = timezone.localtime(self.cita.inicio)
        return {
            "mascota": self.cita.mascota, "profesional": self.cita.profesional_id,
            "fecha": local.date(), "hora": local.strftime("%H:%M"), "motivo": self.cita.motivo,
        }

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            titulo_pagina="Reprogramar cita", url_volver=reverse("cita_detalle", args=[self.cita.pk]), **kwargs
        )


class CitaCambiarEstadoView(RolRequeridoMixin, View):
    """POST con el nuevo estado. Las reglas (quién puede qué) las aplica el servicio."""

    def post(self, request, pk):
        cita = get_object_or_404(servicios.citas_visibles(request.user), pk=pk)
        nuevo = request.POST.get("estado", "")
        if nuevo not in EstadoCita.values:
            messages.error(request, "Estado no válido.")
            return redirect("cita_detalle", pk=pk)
        try:
            servicios.cambiar_estado(cita, nuevo, usuario=request.user, comentario=request.POST.get("comentario", "")[:200])
            messages.success(request, f"La cita quedó «{EstadoCita(nuevo).label}».")
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        except PermissionDenied as error:
            messages.error(request, str(error) or "No tienes permiso para esta acción.")
        return redirect("cita_detalle", pk=pk)


class CitaEliminarView(RolRequeridoMixin, View):
    """Solo el administrador puede borrar una cita (y solo si no tiene atención clínica)."""

    roles_permitidos = (Rol.ADMINISTRADOR,)

    def get(self, request, pk):
        cita = get_object_or_404(servicios.citas_visibles(request.user), pk=pk)
        return render(request, "crud/confirmar_eliminar.html", {
            "titulo_pagina": "Eliminar cita",
            "mensaje_confirmacion": f"Se eliminará la cita de {cita.mascota.nombre} del {timezone.localtime(cita.inicio):%d/%m/%Y %H:%M}. Normalmente conviene cancelarla en vez de eliminarla.",
            "texto_boton": "Eliminar", "url_volver": reverse("cita_detalle", args=[pk]),
        })

    def post(self, request, pk):
        from django.db.models import ProtectedError

        cita = get_object_or_404(servicios.citas_visibles(request.user), pk=pk)
        try:
            cita.delete()
        except ProtectedError:
            messages.error(request, "La cita tiene una atención clínica registrada y no puede eliminarse.")
            return redirect("cita_detalle", pk=pk)
        messages.success(request, "Cita eliminada.")
        return redirect("cita_lista")


# ------------------------------------------------------------
# DISPONIBILIDAD SEMANAL Y BLOQUEOS
# El veterinario trabaja siempre sobre SU profesional; el admin elige.
# ------------------------------------------------------------
class AgendaPropiaMixin(RolRequeridoMixin):
    roles_permitidos = AGENDA_PROPIA

    @cached_property
    def profesional_propio(self):
        return _profesional_de(self.request.user)

    def filtrar(self, consulta):
        propio = self.profesional_propio
        return consulta.filter(profesional=propio) if propio else consulta


class DisponibilidadListaView(AgendaPropiaMixin, ListView):
    template_name = "agenda/disponibilidad_lista.html"
    context_object_name = "bloques"

    def get_queryset(self):
        return self.filtrar(DisponibilidadSemanal.objects.select_related("profesional__usuario"))

    def get_context_data(self, **kwargs):
        bloqueos = self.filtrar(BloqueoAgenda.objects.select_related("profesional__usuario")).filter(fin__gte=timezone.now())
        return super().get_context_data(bloqueos=bloqueos, **kwargs)


class _FormularioAgendaPropia(AgendaPropiaMixin, FormView):
    template_name = "crud/formulario.html"
    modelo = None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["profesional"] = self.profesional_propio
        kwargs["instance"] = self.objeto
        return kwargs

    objeto = None

    def form_valid(self, form):
        form.save()
        messages.success(self.request, self.mensaje_exito)
        return redirect("disponibilidad_lista")

    def get_context_data(self, **kwargs):
        return super().get_context_data(titulo_pagina=self.titulo, url_volver=reverse("disponibilidad_lista"), **kwargs)


class DisponibilidadCrearView(_FormularioAgendaPropia):
    form_class = DisponibilidadForm
    titulo = "Nuevo bloque de disponibilidad"
    mensaje_exito = "Bloque de disponibilidad guardado."


class DisponibilidadEditarView(_FormularioAgendaPropia):
    form_class = DisponibilidadForm
    titulo = "Editar bloque de disponibilidad"
    mensaje_exito = "Bloque de disponibilidad actualizado."

    @cached_property
    def objeto(self):
        return get_object_or_404(self.filtrar(DisponibilidadSemanal.objects.all()), pk=self.kwargs["pk"])


class BloqueoCrearView(_FormularioAgendaPropia):
    form_class = BloqueoForm
    titulo = "Nuevo bloqueo de agenda"
    mensaje_exito = "Bloqueo registrado."


class BloqueoEditarView(_FormularioAgendaPropia):
    form_class = BloqueoForm
    titulo = "Editar bloqueo de agenda"
    mensaje_exito = "Bloqueo actualizado."

    @cached_property
    def objeto(self):
        return get_object_or_404(self.filtrar(BloqueoAgenda.objects.all()), pk=self.kwargs["pk"])


class _EliminarAgendaPropia(AgendaPropiaMixin, View):
    modelo = None
    descripcion = ""

    def _objeto(self, pk):
        return get_object_or_404(self.filtrar(self.modelo.objects.all()), pk=pk)

    def get(self, request, pk):
        return render(request, "crud/confirmar_eliminar.html", {
            "titulo_pagina": f"Eliminar {self.descripcion}",
            "mensaje_confirmacion": f"Se eliminará: {self._objeto(pk)}. Las citas ya agendadas no se modifican.",
            "texto_boton": "Eliminar", "url_volver": reverse("disponibilidad_lista"),
        })

    def post(self, request, pk):
        self._objeto(pk).delete()
        messages.success(request, f"{self.descripcion.capitalize()} eliminado.")
        return redirect("disponibilidad_lista")


class DisponibilidadEliminarView(_EliminarAgendaPropia):
    modelo = DisponibilidadSemanal
    descripcion = "bloque de disponibilidad"


class BloqueoEliminarView(_EliminarAgendaPropia):
    modelo = BloqueoAgenda
    descripcion = "bloqueo de agenda"
