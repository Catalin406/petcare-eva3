# ============================================================
# VACUNACION/MODELS.PY / VACUNAS, CONTROLES Y RECORDATORIOS
# Resuelve el "falta de seguimiento de vacunas": cada aplicación calcula
# sola su próxima dosis y el comando generar_recordatorios avisa al tutor.
# ============================================================
from datetime import timedelta

from django.db import models
from django.db.models import Q
from django.utils import timezone

from clientes.models import Especie
from core.validadores import validar_no_futura


class Vacuna(models.Model):
    """Catálogo de vacunas."""

    nombre = models.CharField(max_length=100, unique=True)
    # Vacío = aplica a cualquier especie.
    especie_aplicable = models.CharField(max_length=10, choices=Especie.choices, blank=True)
    periodicidad_dias = models.PositiveIntegerField(
        "periodicidad (días)", help_text="Cada cuántos días se repite la dosis (ej.: 365 = anual)."
    )
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "vacuna"
        verbose_name_plural = "vacunas"
        ordering = ["nombre"]
        constraints = [
            models.CheckConstraint(condition=Q(periodicidad_dias__gt=0), name="vacuna_periodicidad_positiva"),
        ]

    def __str__(self):
        return self.nombre


class RegistroVacuna(models.Model):
    mascota = models.ForeignKey("clientes.Mascota", on_delete=models.PROTECT, related_name="registros_vacuna")
    vacuna = models.ForeignKey(Vacuna, on_delete=models.PROTECT, related_name="registros")
    fecha_aplicacion = models.DateField(validators=[validar_no_futura])
    lote = models.CharField(max_length=40, blank=True)
    veterinario = models.ForeignKey(
        "agenda.Profesional", on_delete=models.PROTECT, null=True, blank=True, related_name="vacunas_aplicadas"
    )
    # Se calcula sola en save(); es de solo lectura en formularios y API.
    proxima_dosis = models.DateField(editable=False, db_index=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "registro de vacuna"
        verbose_name_plural = "registros de vacunas"
        ordering = ["-fecha_aplicacion"]
        constraints = [
            models.UniqueConstraint(
                fields=["mascota", "vacuna", "fecha_aplicacion"],
                name="registro_vacuna_unico_por_dia",
                violation_error_message="Esa vacuna ya está registrada para la mascota en esa fecha.",
            ),
            models.CheckConstraint(
                condition=Q(proxima_dosis__gte=models.F("fecha_aplicacion")), name="registro_proxima_no_anterior"
            ),
        ]

    def __str__(self):
        return f"{self.vacuna} a {self.mascota.nombre} ({self.fecha_aplicacion:%d/%m/%Y})"

    def calcular_proxima_dosis(self):
        return self.fecha_aplicacion + timedelta(days=self.vacuna.periodicidad_dias)

    def save(self, *args, **kwargs):
        self.proxima_dosis = self.calcular_proxima_dosis()
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"proxima_dosis"}
        super().save(*args, **kwargs)


class ControlPeriodico(models.Model):
    mascota = models.ForeignKey("clientes.Mascota", on_delete=models.PROTECT, related_name="controles")
    motivo = models.CharField(max_length=150)
    fecha_programada = models.DateField(db_index=True)
    realizado = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "control periódico"
        verbose_name_plural = "controles periódicos"
        ordering = ["fecha_programada"]

    def __str__(self):
        return f"{self.motivo} · {self.mascota.nombre} ({self.fecha_programada:%d/%m/%Y})"


class TipoRecordatorio(models.TextChoices):
    VACUNA = "VACUNA", "Vacuna"
    CONTROL = "CONTROL", "Control"


class EstadoRecordatorio(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    ENVIADO = "ENVIADO", "Enviado"
    COMPLETADO = "COMPLETADO", "Completado"
    VENCIDO = "VENCIDO", "Vencido"


class CanalRecordatorio(models.TextChoices):
    EMAIL = "EMAIL", "Correo electrónico"
    SISTEMA = "SISTEMA", "Solo en el sistema"


class Recordatorio(models.Model):
    mascota = models.ForeignKey("clientes.Mascota", on_delete=models.CASCADE, related_name="recordatorios")
    tipo = models.CharField(max_length=8, choices=TipoRecordatorio.choices)
    fecha_objetivo = models.DateField(db_index=True)
    estado = models.CharField(
        max_length=10, choices=EstadoRecordatorio.choices, default=EstadoRecordatorio.PENDIENTE, db_index=True
    )
    canal = models.CharField(max_length=8, choices=CanalRecordatorio.choices, default=CanalRecordatorio.EMAIL)
    # Origen: exactamente uno de los dos, según el tipo.
    registro_vacuna = models.ForeignKey(
        RegistroVacuna, on_delete=models.CASCADE, null=True, blank=True, related_name="recordatorios"
    )
    control = models.ForeignKey(
        ControlPeriodico, on_delete=models.CASCADE, null=True, blank=True, related_name="recordatorios"
    )
    enviado_en = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "recordatorio"
        verbose_name_plural = "recordatorios"
        ordering = ["fecha_objetivo"]
        constraints = [
            # Idempotencia en la base de datos: el comando no puede duplicar un aviso.
            models.UniqueConstraint(
                fields=["registro_vacuna", "fecha_objetivo"], condition=Q(registro_vacuna__isnull=False),
                name="recordatorio_unico_por_vacuna",
            ),
            models.UniqueConstraint(
                fields=["control", "fecha_objetivo"], condition=Q(control__isnull=False),
                name="recordatorio_unico_por_control",
            ),
            # Coherencia tipo/origen: VACUNA lleva registro_vacuna; CONTROL lleva control.
            models.CheckConstraint(
                condition=(
                    Q(tipo="VACUNA", registro_vacuna__isnull=False, control__isnull=True)
                    | Q(tipo="CONTROL", control__isnull=False, registro_vacuna__isnull=True)
                ),
                name="recordatorio_origen_coherente",
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} de {self.mascota.nombre} para el {self.fecha_objetivo:%d/%m/%Y}"

    @property
    def dias_restantes(self):
        """Negativo = ya pasó la fecha."""
        return (self.fecha_objetivo - timezone.localdate()).days

    @property
    def descripcion(self):
        if self.tipo == TipoRecordatorio.VACUNA:
            return f"Dosis de {self.registro_vacuna.vacuna.nombre}"
        return self.control.motivo
