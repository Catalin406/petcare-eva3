# ============================================================
# CLIENTES/ADMIN.PY / ADMINISTRACIÓN DE TUTORES Y MASCOTAS
# Las mascotas se ven dentro del tutor (inline). Una mascota con
# historial clínico no se puede eliminar desde aquí: se desactiva.
# ============================================================
from django import forms
from django.contrib import admin
from django.db import models
from django.db.models import Count

from core.admin import insignia, insignia_activo

from . import servicios
from .models import Mascota, Tutor


class MascotaInline(admin.TabularInline):
    model = Mascota
    extra = 0
    fields = ("nombre", "especie", "sexo", "fecha_nacimiento", "activa")
    show_change_link = True
    # El alta de mascotas se hace en su propia pantalla (tiene foto y más validaciones).
    can_delete = False


@admin.register(Tutor)
class TutorAdmin(admin.ModelAdmin):
    list_display = ("nombre_completo", "rut", "correo", "telefono", "total_mascotas", "cuenta")
    list_filter = ("usuario__is_active",)
    search_fields = ("rut", "usuario__first_name", "usuario__last_name", "usuario__email", "telefono")
    date_hierarchy = "creado_en"
    readonly_fields = ("creado_en", "actualizado_en")
    raw_id_fields = ("usuario",)
    inlines = [MascotaInline]
    actions = ["desactivar_cuentas", "activar_cuentas"]
    fieldsets = (
        ("Cuenta de acceso", {"fields": ("usuario",)}),
        ("Datos del tutor", {"fields": ("rut", "telefono", "direccion")}),
        ("Auditoría", {"fields": ("creado_en", "actualizado_en")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("usuario").annotate(_mascotas=Count("mascotas"))

    @admin.display(description="Nombre", ordering="usuario__last_name")
    def nombre_completo(self, tutor):
        return tutor.nombre_completo

    @admin.display(description="Correo", ordering="usuario__email")
    def correo(self, tutor):
        return tutor.email

    @admin.display(description="Mascotas", ordering="_mascotas")
    def total_mascotas(self, tutor):
        return tutor._mascotas

    @admin.display(description="Cuenta", ordering="usuario__is_active")
    def cuenta(self, tutor):
        return insignia_activo(tutor.usuario.is_active, "Activa", "Desactivada")

    @admin.action(description="Desactivar la cuenta de los tutores seleccionados")
    def desactivar_cuentas(self, request, queryset):
        n = 0
        for tutor in queryset.select_related("usuario"):
            tutor.usuario.is_active = False
            tutor.usuario.save(update_fields=["is_active"])
            n += 1
        self.message_user(request, f"{n} cuenta(s) de tutor desactivada(s).")

    @admin.action(description="Activar la cuenta de los tutores seleccionados")
    def activar_cuentas(self, request, queryset):
        n = 0
        for tutor in queryset.select_related("usuario"):
            tutor.usuario.is_active = True
            tutor.usuario.save(update_fields=["is_active"])
            n += 1
        self.message_user(request, f"{n} cuenta(s) de tutor activada(s).")

    def has_delete_permission(self, request, obj=None):
        # Un tutor con mascotas no se borra (PROTECT); se desactiva.
        return obj is None or not obj.mascotas.exists()


@admin.register(Mascota)
class MascotaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "especie_insignia", "raza", "tutor", "edad", "microchip", "estado")
    list_filter = ("especie", "sexo", "activa")
    search_fields = ("nombre", "raza", "microchip", "tutor__rut", "tutor__usuario__first_name", "tutor__usuario__last_name")
    date_hierarchy = "creada_en"
    readonly_fields = ("edad", "creada_en", "actualizada_en")
    raw_id_fields = ("tutor",)
    list_select_related = ("tutor__usuario",)
    actions = ["desactivar", "activar"]
    # FileInput: el widget por defecto intenta mostrar foto.url y las fotos son privadas.
    formfield_overrides = {models.ImageField: {"widget": forms.FileInput}}
    fieldsets = (
        ("Identificación", {"fields": ("tutor", "nombre", "especie", "raza", "sexo", "fecha_nacimiento", "edad")}),
        ("Datos físicos", {"fields": ("peso", "color_senas", "microchip", "foto")}),
        ("Estado", {"fields": ("activa",)}),
        ("Auditoría", {"fields": ("creada_en", "actualizada_en")}),
    )

    @admin.display(description="Especie", ordering="especie")
    def especie_insignia(self, mascota):
        return insignia(mascota.get_especie_display(), "especie")

    @admin.display(description="Edad", ordering="fecha_nacimiento")
    def edad(self, mascota):
        return mascota.edad_texto

    @admin.display(description="Estado", ordering="activa")
    def estado(self, mascota):
        return insignia_activo(mascota.activa, "Activa", "Inactiva")

    @admin.action(description="Desactivar mascotas seleccionadas")
    def desactivar(self, request, queryset):
        self.message_user(request, f"{queryset.update(activa=False)} mascota(s) desactivada(s).")

    @admin.action(description="Activar mascotas seleccionadas")
    def activar(self, request, queryset):
        self.message_user(request, f"{queryset.update(activa=True)} mascota(s) activada(s).")

    def has_delete_permission(self, request, obj=None):
        # No se elimina una mascota con historial clínico: se desactiva.
        return obj is None or not servicios.tiene_historial_clinico(obj)
