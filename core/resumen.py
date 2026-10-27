# ============================================================
# CORE/RESUMEN.PY / DATOS DE LA PÁGINA DE INICIO SEGÚN EL ROL
# Cada rol ve un resumen distinto. Se completa por fase, a medida
# que existen los modelos de agenda, clínica y vacunación.
# ============================================================


def resumen_para(usuario):
    return {}


def contexto_mascota(usuario, mascota):
    """Qué botones y secciones ve cada rol en el detalle de una mascota."""
    return {
        "puede_editar": usuario.rol in ("ADMINISTRADOR", "RECEPCIONISTA"),
        "puede_ver_tutor": usuario.rol in ("ADMINISTRADOR", "RECEPCIONISTA"),
        "puede_ver_ficha": usuario.rol in ("ADMINISTRADOR", "VETERINARIO", "TUTOR"),
        "puede_pedir_cita": usuario.rol in ("ADMINISTRADOR", "RECEPCIONISTA", "TUTOR") and mascota.activa,
    }
