# ============================================================
# AGENDA/ADMIN.PY / ADMINISTRACIÓN DE PROFESIONALES, DISPONIBILIDAD Y CITAS
# El estado de una cita NO se edita a mano: cambia con acciones que
# pasan por servicios.cambiar_estado (transiciones válidas + historial).
# El formulario de la cita aplica las mismas validaciones que la web y la API.
# ============================================================
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count

from core.admin import insignia, insignia_activo

from . import servicios
from .models import BloqueoAgenda, Cita, DisponibilidadSemanal, EstadoCita, HistorialCita, Profesional


class DisponibilidadInline(admin.TabularInline):
    model = DisponibilidadSemanal
    extra = 0
    fields = ("dia_semana", "hora_inicio", "hora_fin", "duracion_bloque_min")
    ordering = ("dia_semana", "hora_inicio")


class BloqueoInline(admin.TabularInline):
    model = BloqueoAgenda
    extra = 0
    fields = ("inicio", "fin", "motivo")


@admin.register(Profesional)
class ProfesionalAdmin(admin.ModelAdmin):
    list_display = ("nombre", "especialidad", "estado", "total_citas", "bloques_semanales")
    list_filter = ("activo", "especialidad")
    search_fields = ("usuario__first_name", "usuario__last_name", "usuario__email", "especialidad")
    raw_id_fields = ("usuario",)
    inlines = [DisponibilidadInline, BloqueoInline]
    actions = ["activar", "desactivar"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("usuario").annotate(
            _citas=Count("citas", distinct=True), _bloques=Count("disponibilidades", distinct=True)
        )

    @admin.display(description="Estado", ordering="activo")
    def estado(self, profesional):
        return insignia_activo(profesional.activo)

    @admin.display(description="Citas", ordering="_citas")
    def total_citas(self, profesional):
        return profesional._citas

    @admin.display(description="Franjas por semana", ordering="_bloques")
    def bloques_semanales(self, profesional):
        return profesional._bloques

    @admin.action(description="Activar profesionales seleccionados")
    def activar(self, request, queryset):
        self.message_user(request, f"{queryset.update(activo=True)} profesional(es) activado(s).")

    @admin.action(description="Desactivar profesionales seleccionados")
    def desactivar(self, request, queryset):
        self.message_user(request, f"{queryset.update(activo=False)} profesional(es) desactivado(s).")


@admin.register(DisponibilidadSemanal)
class DisponibilidadSemanalAdmin(admin.ModelAdmin):
    list_display = ("profesional", "dia_semana", "hora_inicio", "hora_fin", "duracion_bloque_min")
    list_filter = ("dia_semana", "profesional")
    search_fields = ("profesional__usuario__first_name", "profesional__usuario__last_name")
    list_select_related = ("profesional__usuario",)
    ordering = ("profesional", "dia_semana", "hora_inicio")


@admin.register(BloqueoAgenda)
class BloqueoAgendaAdmin(admin.ModelAdmin):
    list_display = ("profesional", "motivo", "inicio", "fin")
    list_filter = ("profesional",)
    search_fields = ("motivo", "profesional__usuario__last_name")
    date_hierarchy = "inicio"
    list_select_related = ("profesional__usuario",)


class HistorialInline(admin.TabularInline):
    model = HistorialCita
    extra = 0
    can_delete = False
    fields = ("fecha", "estado_anterior", "estado_nuevo", "usuario", "comentario")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class CitaAdminForm(forms.ModelForm):
    """Reutiliza las reglas de agendamiento: sin solapes, dentro de la disponibilidad, no en el pasado."""

    class Meta:
        model = Cita
        fields = "__all__"

    def _get_validation_exclusions(self):
        # "estado" no está en el formulario (cambia con acciones), pero la condición de las
        # ExclusionConstraint lo necesita para validar: se toma del propio objeto.
        exclusiones = super()._get_validation_exclusions()
        exclusiones.discard("estado")
        return exclusiones

    def clean(self):
        datos = super().clean()
        campos_de_horario = {"mascota", "profesional", "inicio", "fin"}
        if self.errors or not datos.get("inicio"):
            return datos
        cambia_horario = self.instance.pk is None or campos_de_horario & set(self.changed_data)
        if cambia_horario and self.instance.estado != EstadoCita.CANCELADA:
            try:
                servicios.validar_cita(
                    mascota=datos["mascota"], profesional=datos["profesional"], inicio=datos["inicio"],
                    fin=datos["fin"], excluir=self.instance if self.instance.pk else None,
                )
            except ValidationError as error:
                raise ValidationError(error.messages)
        return datos


@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    form = CitaAdminForm
    list_display = ("inicio", "mascota", "profesional", "motivo", "estado_insignia", "creada_por")
    list_filter = ("estado", "profesional", "inicio")
    search_fields = ("mascota__nombre", "motivo", "mascota__tutor__rut", "profesional__usuario__last_name")
    date_hierarchy = "inicio"
    list_select_related = ("mascota", "profesional__usuario", "creada_por")
    raw_id_fields = ("mascota",)
    readonly_fields = ("estado_insignia", "creada_por", "creada_en", "actualizada_en")
    inlines = [HistorialInline]
    actions = ["confirmar", "marcar_no_asistio", "cancelar"]
    fieldsets = (
        ("Cita", {"fields": ("mascota", "profesional", "inicio", "fin", "motivo")}),
        ("Estado", {"fields": ("estado_insignia",), "description": "El estado cambia con las acciones de la lista (queda en el historial)."}),
        ("Auditoría", {"fields": ("creada_por", "creada_en", "actualizada_en")}),
    )

    @admin.display(description="Estado", ordering="estado")
    def estado_insignia(self, cita):
        return insignia(cita.get_estado_display(), cita.estado.lower()) if cita.pk else "—"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.creada_por = request.user
        super().save_model(request, obj, form, change)
        if not change:
            servicios._registrar_historial(obj, "", obj.estado, request.user, "Cita creada desde el Admin")

    def _transicion(self, request, queryset, nuevo):
        hechas = 0
        for cita in queryset:
            try:
                servicios.cambiar_estado(cita, nuevo, usuario=request.user, comentario="Cambio masivo desde el Admin")
                hechas += 1
            except (ValidationError, PermissionDenied) as error:
                detalle = " ".join(error.messages) if hasattr(error, "messages") else str(error)
                self.message_user(request, f"{cita}: {detalle}", messages.WARNING)
        if hechas:
            self.message_user(request, f"{hechas} cita(s) → {EstadoCita(nuevo).label}.", messages.SUCCESS)

    @admin.action(description="Confirmar citas seleccionadas")
    def confirmar(self, request, queryset):
        self._transicion(request, queryset, EstadoCita.CONFIRMADA)

    @admin.action(description="Marcar «No asistió»")
    def marcar_no_asistio(self, request, queryset):
        self._transicion(request, queryset, EstadoCita.NO_ASISTIO)

    @admin.action(description="Cancelar citas seleccionadas")
    def cancelar(self, request, queryset):
        self._transicion(request, queryset, EstadoCita.CANCELADA)


@admin.register(HistorialCita)
class HistorialCitaAdmin(admin.ModelAdmin):
    """Bitácora de solo lectura: se escribe únicamente desde los servicios."""

    list_display = ("fecha", "cita", "estado_anterior", "estado_nuevo", "usuario", "comentario")
    list_filter = ("estado_nuevo",)
    search_fields = ("cita__mascota__nombre", "comentario")
    date_hierarchy = "fecha"
    list_select_related = ("cita__mascota", "usuario")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
