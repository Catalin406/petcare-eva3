# ============================================================
# CORE/ADMIN.PY / MARCA DEL DJANGO ADMIN E INSIGNIAS DE COLOR
# Textos del sitio de administración en español, y utilidades para
# mostrar estados como insignias (format_html: el texto se escapa solo).
# Los colores viven en static/admin/css/petcare_admin.css.
# ============================================================
from django.contrib import admin
from django.utils.html import format_html

admin.site.site_header = "Administración de PetCare"
admin.site.site_title = "PetCare · Administración"
admin.site.index_title = "Gestión de la clínica veterinaria"


def insignia(texto, clase):
    """<span> con color según la clase (pc-programada, pc-activo, ...)."""
    return format_html('<span class="pc-insignia pc-{}">{}</span>', clase, texto)


def insignia_activo(activo, texto_si="Activo", texto_no="Inactivo"):
    return insignia(texto_si if activo else texto_no, "activo" if activo else "inactivo")
