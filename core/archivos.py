# ============================================================
# CORE/ARCHIVOS.PY / ARCHIVOS PRIVADOS (FOTOS Y EXÁMENES)
# Estos archivos son datos clínicos: se guardan FUERA de static y de
# cualquier carpeta pública, sin URL directa. Solo se entregan con
# una vista que verifica login y permisos (entregar_archivo).
# Nginx NUNCA debe exponer la carpeta archivos_privados/.
# ============================================================
import mimetypes
import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, Http404


def almacenamiento_privado():
    # base_url=None: si alguien llama a .url, Django falla en vez de
    # fabricar una ruta pública. Es una función (no una instancia) para
    # que las migraciones no guarden rutas absolutas de esta máquina.
    return FileSystemStorage(location=settings.ARCHIVOS_PRIVADOS_ROOT, base_url=None)


def entregar_archivo(campo_archivo, descargar=False):
    """Responde con el archivo; 404 si no existe. Quien llama ya verificó permisos."""
    if not campo_archivo:
        raise Http404("El registro no tiene archivo.")
    try:
        abierto = campo_archivo.open("rb")
    except FileNotFoundError:
        raise Http404("El archivo ya no está disponible.")
    tipo, _ = mimetypes.guess_type(campo_archivo.name)
    respuesta = FileResponse(
        abierto,
        content_type=tipo or "application/octet-stream",
        as_attachment=descargar,
        filename=os.path.basename(campo_archivo.name),
    )
    # Datos clínicos: que ningún proxy o navegador compartido los guarde.
    respuesta["Cache-Control"] = "private, no-store"
    return respuesta
