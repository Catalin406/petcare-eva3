# ============================================================
# USUARIOS/ADMIN.PY / ADMINISTRACIÓN DE USUARIOS
# is_staff es de solo lectura: lo calcula el rol en Usuario.save().
# ============================================================
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("username", "nombre_visible", "email", "rol", "is_active", "last_login")
    list_filter = ("rol", "is_active")
    search_fields = ("username", "first_name", "last_name", "email")
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
