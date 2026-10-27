# ============================================================
# CLINICA/ADMIN.PY / ADMINISTRACIÓN DE LA FICHA CLÍNICA
# Registro clínico de SOLO LECTURA en el Admin: solo el veterinario crea
# o corrige atenciones (desde la web o la API, donde la cita pasa a
# ATENDIDA en la misma transacción) y nadie las borra. La ficha general
# sí se puede editar. Los adjuntos se enlazan a la vista protegida.
# ============================================================
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from core.admin import insignia

from .models import Atencion, Examen, FichaClinica, Receta


class SoloLecturaMixin:
    def has_add_permission(self, request, *args, **kwargs):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class RecetaInline(SoloLecturaMixin, admin.TabularInline):
    model = Receta
    extra = 0
    fields = ("medicamento", "dosis", "frecuencia", "duracion", "indicaciones")


class ExamenInline(SoloLecturaMixin, admin.TabularInline):
    model = Examen
    extra = 0
    fields = ("tipo", "fecha", "resultado", "adjunto")
    readonly_fields = ("adjunto",)

    @admin.display(description="Adjunto")
    def adjunto(self, examen):
        return _enlace_adjunto(examen)


def _enlace_adjunto(examen):
    # El archivo es privado: el enlace va a la vista con login y permisos, no a /media/.
    if not examen.pk or not examen.archivo:
        return "—"
    return format_html('<a href="{}" target="_blank" rel="noopener">Ver adjunto</a>', reverse("examen_archivo", args=[examen.pk]))


class AtencionInlineFicha(SoloLecturaMixin, admin.TabularInline):
    model = Atencion
    extra = 0
    fields = ("fecha", "veterinario", "diagnostico")
    show_change_link = True


@admin.register(FichaClinica)
class FichaClinicaAdmin(admin.ModelAdmin):
    list_display = ("mascota", "tutor", "alergias_resumen", "total_atenciones", "actualizada_en")
    list_filter = ("mascota__especie",)
    search_fields = ("mascota__nombre", "mascota__tutor__rut", "alergias", "antecedentes")
    date_hierarchy = "creada_en"
    readonly_fields = ("mascota", "creada_en", "actualizada_en")
    list_select_related = ("mascota__tutor__usuario",)
    inlines = [AtencionInlineFicha]

    @admin.display(description="Tutor")
    def tutor(self, ficha):
        return ficha.mascota.tutor.nombre_completo

    @admin.display(description="Alergias")
    def alergias_resumen(self, ficha):
        return ficha.alergias[:50] + ("…" if len(ficha.alergias) > 50 else "") if ficha.alergias else "—"

    @admin.display(description="Atenciones")
    def total_atenciones(self, ficha):
        return ficha.atenciones.count()

    def has_add_permission(self, request):  # la ficha nace sola con la mascota
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Atencion)
class AtencionAdmin(SoloLecturaMixin, admin.ModelAdmin):
    list_display = ("fecha", "mascota", "veterinario", "diagnostico_resumen", "origen")
    list_filter = ("veterinario", "fecha")
    search_fields = ("ficha__mascota__nombre", "diagnostico", "anamnesis", "veterinario__usuario__last_name")
    date_hierarchy = "fecha"
    list_select_related = ("ficha__mascota", "veterinario__usuario", "cita")
    readonly_fields = ("creada_en", "actualizada_en")
    inlines = [RecetaInline, ExamenInline]

    @admin.display(description="Mascota", ordering="ficha__mascota__nombre")
    def mascota(self, atencion):
        return atencion.ficha.mascota

    @admin.display(description="Diagnóstico")
    def diagnostico_resumen(self, atencion):
        return atencion.diagnostico[:60] + ("…" if len(atencion.diagnostico) > 60 else "")

    @admin.display(description="Origen")
    def origen(self, atencion):
        return insignia("Con cita", "confirmada") if atencion.cita_id else insignia("Urgencia", "cancelada")


@admin.register(Receta)
class RecetaAdmin(SoloLecturaMixin, admin.ModelAdmin):
    list_display = ("medicamento", "dosis", "frecuencia", "duracion", "mascota", "fecha")
    list_filter = ("atencion__fecha",)
    search_fields = ("medicamento", "atencion__ficha__mascota__nombre")
    date_hierarchy = "atencion__fecha"
    list_select_related = ("atencion__ficha__mascota",)

    @admin.display(description="Mascota")
    def mascota(self, receta):
        return receta.atencion.ficha.mascota

    @admin.display(description="Fecha", ordering="atencion__fecha")
    def fecha(self, receta):
        return receta.atencion.fecha


@admin.register(Examen)
class ExamenAdmin(SoloLecturaMixin, admin.ModelAdmin):
    list_display = ("tipo", "fecha", "mascota", "adjunto")
    list_filter = ("tipo", "fecha")
    search_fields = ("tipo", "resultado", "atencion__ficha__mascota__nombre")
    date_hierarchy = "fecha"
    list_select_related = ("atencion__ficha__mascota",)
    readonly_fields = ("adjunto",)
    fields = ("atencion", "tipo", "fecha", "resultado", "adjunto")

    @admin.display(description="Mascota")
    def mascota(self, examen):
        return examen.atencion.ficha.mascota

    @admin.display(description="Adjunto")
    def adjunto(self, examen):
        return _enlace_adjunto(examen)
