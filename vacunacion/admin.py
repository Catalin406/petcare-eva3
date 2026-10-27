# ============================================================
# VACUNACION/ADMIN.PY / ADMINISTRACIÓN DE VACUNAS, CONTROLES Y RECORDATORIOS
# ============================================================
from django.contrib import admin
from django.utils import timezone

from core.admin import insignia, insignia_activo

from . import servicios
from .models import ControlPeriodico, EstadoRecordatorio, Recordatorio, RegistroVacuna, Vacuna


@admin.register(Vacuna)
class VacunaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "especie_aplicable", "periodicidad", "estado", "aplicaciones")
    list_filter = ("especie_aplicable", "activa")
    search_fields = ("nombre",)
    actions = ["activar", "desactivar"]

    @admin.display(description="Periodicidad", ordering="periodicidad_dias")
    def periodicidad(self, vacuna):
        return f"cada {vacuna.periodicidad_dias} días"

    @admin.display(description="Estado", ordering="activa")
    def estado(self, vacuna):
        return insignia_activo(vacuna.activa, "Activa", "Desactivada")

    @admin.display(description="Aplicaciones")
    def aplicaciones(self, vacuna):
        return vacuna.registros.count()

    @admin.action(description="Activar vacunas seleccionadas")
    def activar(self, request, queryset):
        self.message_user(request, f"{queryset.update(activa=True)} vacuna(s) activada(s).")

    @admin.action(description="Desactivar vacunas seleccionadas")
    def desactivar(self, request, queryset):
        self.message_user(request, f"{queryset.update(activa=False)} vacuna(s) desactivada(s).")

    def has_delete_permission(self, request, obj=None):
        return obj is None or not obj.registros.exists()


@admin.register(RegistroVacuna)
class RegistroVacunaAdmin(admin.ModelAdmin):
    list_display = ("mascota", "vacuna", "fecha_aplicacion", "lote", "proxima_dosis", "situacion", "veterinario")
    list_filter = ("vacuna", "mascota__especie", "fecha_aplicacion")
    search_fields = ("mascota__nombre", "vacuna__nombre", "lote", "mascota__tutor__rut")
    date_hierarchy = "fecha_aplicacion"
    list_select_related = ("mascota", "vacuna", "veterinario__usuario")
    readonly_fields = ("proxima_dosis", "creado_en")
    raw_id_fields = ("mascota",)
    fields = ("mascota", "vacuna", "fecha_aplicacion", "lote", "veterinario", "proxima_dosis", "creado_en")

    @admin.display(description="Próxima dosis")
    def situacion(self, registro):
        dias = (registro.proxima_dosis - timezone.localdate()).days
        if dias < 0:
            return insignia(f"Vencida hace {-dias} d", "vencido")
        if dias <= 7:
            return insignia(f"En {dias} d", "pendiente")
        if dias <= 30:
            return insignia(f"En {dias} d", "confirmada")
        return insignia("Vigente", "atendida")

    def save_model(self, request, obj, form, change):
        # La próxima dosis la calcula el modelo; el recordatorio anterior se cierra aquí también.
        super().save_model(request, obj, form, change)
        Recordatorio.objects.filter(
            registro_vacuna__mascota=obj.mascota, registro_vacuna__vacuna=obj.vacuna,
            registro_vacuna__fecha_aplicacion__lt=obj.fecha_aplicacion,
        ).exclude(estado=EstadoRecordatorio.COMPLETADO).update(estado=EstadoRecordatorio.COMPLETADO)


@admin.register(ControlPeriodico)
class ControlPeriodicoAdmin(admin.ModelAdmin):
    list_display = ("fecha_programada", "mascota", "motivo", "estado")
    list_filter = ("realizado", "fecha_programada")
    search_fields = ("mascota__nombre", "motivo")
    date_hierarchy = "fecha_programada"
    list_select_related = ("mascota",)
    raw_id_fields = ("mascota",)
    readonly_fields = ("creado_en",)
    actions = ["marcar_realizado"]

    @admin.display(description="Estado", ordering="realizado")
    def estado(self, control):
        return insignia("Realizado", "completado") if control.realizado else insignia("Pendiente", "pendiente")

    @admin.action(description="Marcar controles como realizados")
    def marcar_realizado(self, request, queryset):
        for control in queryset:
            servicios.marcar_control_realizado(control)
        self.message_user(request, f"{queryset.count()} control(es) marcado(s) como realizado(s).")


@admin.register(Recordatorio)
class RecordatorioAdmin(admin.ModelAdmin):
    list_display = ("fecha_objetivo", "mascota", "tipo", "detalle", "estado_insignia", "canal", "enviado_en")
    list_filter = ("estado", "tipo", "canal", "fecha_objetivo")
    search_fields = ("mascota__nombre", "mascota__tutor__rut", "mascota__tutor__usuario__email")
    date_hierarchy = "fecha_objetivo"
    list_select_related = ("mascota", "registro_vacuna__vacuna", "control")
    readonly_fields = ("creado_en", "enviado_en")
    actions = ["completar", "generar_ahora"]

    @admin.display(description="Detalle")
    def detalle(self, recordatorio):
        return recordatorio.descripcion

    @admin.display(description="Estado", ordering="estado")
    def estado_insignia(self, recordatorio):
        return insignia(recordatorio.get_estado_display(), recordatorio.estado.lower())

    @admin.action(description="Marcar como completados")
    def completar(self, request, queryset):
        self.message_user(request, f"{queryset.update(estado=EstadoRecordatorio.COMPLETADO)} recordatorio(s) completado(s).")

    @admin.action(description="Ejecutar ahora la generación de recordatorios")
    def generar_ahora(self, request, queryset):
        r = servicios.generar_recordatorios()
        self.message_user(
            request, f"{r['creados']} creados, {r['vencidos']} vencidos, {r['enviados']} correos enviados."
        )
