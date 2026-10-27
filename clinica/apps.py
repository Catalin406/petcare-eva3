from django.apps import AppConfig


class ClinicaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "clinica"
    verbose_name = "Ficha clínica"

    def ready(self):
        # Registra la señal que crea la ficha al crear la mascota.
        from . import senales  # noqa: F401
