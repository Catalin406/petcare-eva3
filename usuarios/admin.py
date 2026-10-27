# ============================================================
# USUARIOS/ADMIN.PY / ADMINISTRACIÓN DE USUARIOS
# is_staff es de solo lectura: lo calcula el rol en Usuario.save().
# ============================================================
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from core.admin import insignia, insignia_activo

from .models import Rol, Usuario

CLASE_ROL = {
    Rol.ADMINISTRADOR: "admin", Rol.RECEPCIONISTA: "recep", Rol.VETERINARIO: "vet", Rol.TUTOR: "tutor",
}


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("username", "nombre_visible", "email", "rol_insignia", "activo_insignia", "last_login")
    list_filter = ("rol", "is_active")
    search_fields = ("username", "first_name", "last_name", "email")
    date_hierarchy = "date_joined"
    ordering = ("username",)
    readonly_fields = ("is_staff", "last_login", "date_joined")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Datos personales", {"fields": ("first_name", "last_name", "email")}),
        ("Rol y acceso", {"fields": ("rol", "is_active", "is_staff", "is_superuser")}),
        ("Auditoría", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "email", "rol", "password1", "password2")}),
    )
    actions = ["activar_cuentas", "desactivar_cuentas"]

    @admin.display(description="Rol", ordering="rol")
    def rol_insignia(self, usuario):
        return insignia(usuario.get_rol_display(), CLASE_ROL[usuario.rol])

    @admin.display(description="Cuenta", ordering="is_active")
    def activo_insignia(self, usuario):
        return insignia_activo(usuario.is_active, "Activa", "Desactivada")

    @admin.action(description="Activar cuentas seleccionadas")
    def activar_cuentas(self, request, queryset):
        self.message_user(request, f"{queryset.update(is_active=True)} cuenta(s) activada(s).")

    @admin.action(description="Desactivar cuentas seleccionadas")
    def desactivar_cuentas(self, request, queryset):
        # Nunca se desactiva a sí mismo: dejaría el panel sin acceso.
        queryset = queryset.exclude(pk=request.user.pk)
        self.message_user(request, f"{queryset.update(is_active=False)} cuenta(s) desactivada(s).")
