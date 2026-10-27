# ============================================================
# CORE/EXCEPCIONES.PY / ERRORES DE NEGOCIO COMO RESPUESTA 400 EN LA API
# Los servicios lanzan ValidationError de Django (mensajes en español).
# DRF no la convierte sola: este manejador la traduce a un 400 JSON
# uniforme para que la API y la web compartan las mismas reglas.
# ============================================================
from django.core.exceptions import ValidationError as ErrorValidacionDjango
from rest_framework.exceptions import ValidationError
from rest_framework.views import exception_handler


def manejador_excepciones_api(exc, contexto):
    if isinstance(exc, ErrorValidacionDjango):
        detalle = exc.message_dict if hasattr(exc, "error_dict") else exc.messages
        exc = ValidationError(detalle)
    return exception_handler(exc, contexto)
