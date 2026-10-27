# ============================================================
# CORE/CONTEXT_PROCESSORS.PY / DATOS GLOBALES PARA LAS PLANTILLAS
# Inyecta en todas las plantillas el nombre comercial y los datos
# del estudiante (footer), leídos de settings (y por tanto de .env).
# ============================================================
from django.conf import settings


def datos_alumno(request):
    return {
        "ALUMNO_NOMBRE": settings.ALUMNO_NOMBRE,
        "ALUMNO_SECCION": settings.ALUMNO_SECCION,
        "ALUMNO_ANIO": settings.ALUMNO_ANIO,
        "NOMBRE_COMERCIAL": settings.NOMBRE_COMERCIAL,
    }
