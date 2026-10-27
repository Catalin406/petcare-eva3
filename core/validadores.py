# ============================================================
# CORE/VALIDADORES.PY / RUT CHILENO Y ARCHIVOS ADJUNTOS
# ============================================================
import os
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

PATRON_RUT = re.compile(r"^\d{7,8}-[\dK]$")


def calcular_dv(cuerpo):
    """Dígito verificador del RUT (módulo 11, serie 2-7 de derecha a izquierda)."""
    suma = 0
    multiplicador = 2
    for digito in reversed(cuerpo):
        suma += int(digito) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1
    resto = 11 - (suma % 11)
    if resto == 11:
        return "0"
    if resto == 10:
        return "K"
    return str(resto)


def normalizar_rut(valor):
    """'12.345.678-5' / '123456785' / '12345678-k' -> '12345678-5' (sin puntos, DV en mayúscula)."""
    limpio = re.sub(r"[.\s-]", "", str(valor or "")).upper()
    if len(limpio) < 2:
        return limpio
    return f"{limpio[:-1]}-{limpio[-1]}"


def validar_rut(valor):
    """Valida formato y dígito verificador. Acepta el RUT con o sin puntos/guion."""
    rut = normalizar_rut(valor)
    if not PATRON_RUT.match(rut):
        raise ValidationError("El RUT debe tener 7 u 8 dígitos y un dígito verificador (ej.: 12.345.678-5).")
    cuerpo, dv = rut.split("-")
    if calcular_dv(cuerpo) != dv:
        raise ValidationError("El RUT no es válido: el dígito verificador no corresponde.")


@deconstructible
class ValidadorArchivo:
    """Valida extensión y tamaño de un adjunto (exámenes, fotos)."""

    def __init__(self, extensiones, max_mb=None):
        self.extensiones = tuple(e.lower() for e in extensiones)
        self.max_mb = max_mb

    def __call__(self, archivo):
        extension = os.path.splitext(archivo.name)[1].lower().lstrip(".")
        if extension not in self.extensiones:
            raise ValidationError(
                "Tipo de archivo no permitido (.%(ext)s). Formatos válidos: %(validos)s.",
                params={"ext": extension or "sin extensión", "validos": ", ".join(self.extensiones)},
            )
        limite_mb = self.max_mb or settings.ARCHIVO_MAX_MB
        if archivo.size > limite_mb * 1024 * 1024:
            raise ValidationError("El archivo pesa demasiado: el máximo permitido es %(mb)s MB.", params={"mb": limite_mb})

    def __eq__(self, otro):
        return isinstance(otro, ValidadorArchivo) and self.extensiones == otro.extensiones and self.max_mb == otro.max_mb


validar_adjunto_examen = ValidadorArchivo(["pdf", "jpg", "jpeg", "png"])
validar_foto = ValidadorArchivo(["jpg", "jpeg", "png", "webp"])
