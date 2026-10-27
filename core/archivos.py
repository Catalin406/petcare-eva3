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


class AlmacenamientoPrivado(FileSystemStorage):
    """
    Guarda en ARCHIVOS_PRIVADOS_ROOT, leído de settings en CADA uso (no al importar),
    para que las pruebas puedan apuntar a una carpeta temporal.
    Pedir .url falla a propósito: estos archivos NO tienen ruta pública.
    """

    def url(self, name):
        raise ValueError("Los archivos privados no tienen URL pública: se entregan con una vista protegida.")

    @property
    def base_location(self):
        return settings.ARCHIVOS_PRIVADOS_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)


def almacenamiento_privado():
    # Función (no instancia) para que las migraciones no guarden rutas absolutas de esta máquina.
    return AlmacenamientoPrivado()


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
