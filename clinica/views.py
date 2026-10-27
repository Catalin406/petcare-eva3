# ============================================================
# CLINICA/VIEWS.PY / VISTAS WEB DE LA FICHA CLÍNICA
# Lectura: administrador, veterinario y tutor (solo SUS mascotas).
# Recepción NO entra a datos clínicos (403).
# Escritura de atenciones: solo VETERINARIO. Nadie borra atenciones.
# ============================================================
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import TemplateView

from agenda.models import Cita, Profesional
from clientes.servicios import mascotas_visibles
from core.archivos import entregar_archivo
from core.mixins import RolRequeridoMixin
from usuarios.models import Rol

from . import servicios
from .forms import AtencionForm, ExamenFormSet, FichaForm, RecetaFormSet, datos_de_formset
from .models import Atencion, Examen, Receta

LECTURA = servicios.ROLES_CLINICOS


class FichaDetalleView(RolRequeridoMixin, TemplateView):
    """La ficha como línea de tiempo: atenciones, vacunas y controles."""

    roles_permitidos = LECTURA
    template_name = "clinica/ficha_detalle.html"

    def get_context_data(self, **kwargs):
        ficha = get_object_or_404(servicios.fichas_visibles(self.request.user), mascota_id=self.kwargs["mascota_pk"])
        return super().get_context_data(
            ficha=ficha, mascota=ficha.mascota, eventos=servicios.linea_de_tiempo(ficha.mascota),
            puede_editar_ficha=self.request.user.rol in (Rol.ADMINISTRADOR, Rol.VETERINARIO),
            puede_atender=self.request.user.rol == Rol.VETERINARIO and ficha.mascota.activa,
            **kwargs,
        )


class FichaEditarView(RolRequeridoMixin, View):
    roles_permitidos = (Rol.ADMINISTRADOR, Rol.VETERINARIO)

    def _ficha(self, request, mascota_pk):
        return get_object_or_404(servicios.fichas_visibles(request.user), mascota_id=mascota_pk)

    def get(self, request, mascota_pk):
        ficha = self._ficha(request, mascota_pk)
        return self._mostrar(request, ficha, FichaForm(instance=ficha))

    def post(self, request, mascota_pk):
        ficha = self._ficha(request, mascota_pk)
        form = FichaForm(request.POST, instance=ficha)
        if form.is_valid():
            servicios.actualizar_ficha(ficha, usuario=request.user, **form.cleaned_data)
            messages.success(request, "Ficha clínica actualizada.")
            return redirect("ficha_detalle", mascota_pk=mascota_pk)
        return self._mostrar(request, ficha, form)

    def _mostrar(self, request, ficha, form):
        return render(request, "crud/formulario.html", {
            "form": form, "titulo_pagina": f"Datos generales de la ficha de {ficha.mascota.nombre}",
            "url_volver": reverse("ficha_detalle", args=[ficha.mascota_id]),
        })


class AtencionDetalleView(RolRequeridoMixin, TemplateView):
    roles_permitidos = LECTURA
    template_name = "clinica/atencion_detalle.html"

    def get_context_data(self, **kwargs):
        atencion = get_object_or_404(
            servicios.atenciones_visibles(self.request.user).prefetch_related("recetas", "examenes"), pk=self.kwargs["pk"]
        )
        autor = self.request.user.rol == Rol.VETERINARIO and atencion.veterinario.usuario_id == self.request.user.pk
        return super().get_context_data(atencion=atencion, mascota=atencion.ficha.mascota, puede_editar=autor, **kwargs)


class _AtencionFormularioBase(RolRequeridoMixin, View):
    """Formulario de atención con recetas y exámenes (se agregan, no se borran)."""

    roles_permitidos = (Rol.VETERINARIO,)
    template_name = "clinica/atencion_form.html"

    @cached_property
    def profesional(self):
        return get_object_or_404(Profesional, usuario=self.request.user)

    def _formularios(self, request, **kwargs):
        con_cita = kwargs.pop("con_cita", False)
        instance = kwargs.pop("instance", None)
        datos = (request.POST, request.FILES) if request.method == "POST" else (None, None)
        return {
            "form": AtencionForm(datos[0], instance=instance, usuario=request.user, con_cita=con_cita),
            "recetas": RecetaFormSet(datos[0], datos[1], queryset=Receta.objects.none(), prefix="recetas"),
            "examenes": ExamenFormSet(datos[0], datos[1], queryset=Examen.objects.none(), prefix="examenes"),
        }

    def _validos(self, formularios):
        resultados = [f.is_valid() for f in formularios.values()]
        return all(resultados)

    def _mostrar(self, request, formularios, **extra):
        return render(request, self.template_name, {**formularios, "url_volver": self.url_volver, **extra})


class AtencionCrearView(_AtencionFormularioBase):
    """Con ?cita=ID atiende esa cita; con ?mascota=ID registra una urgencia sin cita."""

    @cached_property
    def cita(self):
        pk = self.request.GET.get("cita") or self.request.POST.get("cita")
        if not pk:
            return None
        return get_object_or_404(Cita.objects.select_related("mascota", "profesional"), pk=pk, profesional=self.profesional)

    @property
    def url_volver(self):
        return reverse("cita_detalle", args=[self.cita.pk]) if self.cita else reverse("cita_lista")

    def get(self, request):
        formularios = self._formularios(request, con_cita=self.cita is not None)
        if self.cita is None and request.GET.get("mascota"):
            formularios["form"].initial["mascota"] = request.GET["mascota"]
        return self._mostrar(request, formularios, titulo_pagina=self._titulo(), cita=self.cita)

    def post(self, request):
        formularios = self._formularios(request, con_cita=self.cita is not None)
        if self._validos(formularios):
            form = formularios["form"]
            ficha = (
                self.cita.mascota.ficha if self.cita
                else get_object_or_404(servicios.fichas_visibles(request.user), mascota=form.cleaned_data["mascota"])
            )
            try:
                atencion = servicios.registrar_atencion(
                    veterinario=self.profesional, ficha=ficha, cita=self.cita, datos=form.datos_atencion(),
                    recetas=datos_de_formset(formularios["recetas"]), examenes=datos_de_formset(formularios["examenes"]),
                )
            except ValidationError as error:
                form.add_error(None, error.messages)
            else:
                messages.success(request, "Atención registrada." + (" La cita quedó como atendida." if self.cita else ""))
                return redirect("atencion_detalle", pk=atencion.pk)
        return self._mostrar(request, formularios, titulo_pagina=self._titulo(), cita=self.cita)

    def _titulo(self):
        return f"Atender a {self.cita.mascota.nombre}" if self.cita else "Registrar atención de urgencia"


class AtencionEditarView(_AtencionFormularioBase):
    @cached_property
    def atencion(self):
        return get_object_or_404(servicios.atenciones_visibles(self.request.user), pk=self.kwargs["pk"])

    @property
    def url_volver(self):
        return reverse("atencion_detalle", args=[self.atencion.pk])

    def get(self, request, pk):
        if self.atencion.veterinario.usuario_id != request.user.pk:
            raise PermissionDenied("Solo el veterinario que registró la atención puede modificarla.")
        return self._mostrar(
            request, self._formularios(request, instance=self.atencion),
            titulo_pagina="Corregir atención", atencion=self.atencion,
        )

    def post(self, request, pk):
        formularios = self._formularios(request, instance=self.atencion)
        if self._validos(formularios):
            try:
                servicios.actualizar_atencion(
                    self.atencion, usuario=request.user, datos=formularios["form"].datos_atencion(),
                    recetas=datos_de_formset(formularios["recetas"]), examenes=datos_de_formset(formularios["examenes"]),
                )
            except ValidationError as error:
                formularios["form"].add_error(None, error.messages)
            else:
                messages.success(request, "Atención actualizada.")
                return redirect("atencion_detalle", pk=pk)
        return self._mostrar(request, formularios, titulo_pagina="Corregir atención", atencion=self.atencion)


class ExamenArchivoView(RolRequeridoMixin, View):
    """Entrega el adjunto de un examen solo a quien puede ver esa atención."""

    roles_permitidos = LECTURA

    def get(self, request, pk):
        examen = get_object_or_404(servicios.examenes_visibles(request.user), pk=pk)
        return entregar_archivo(examen.archivo, descargar=request.GET.get("descargar") == "1")
