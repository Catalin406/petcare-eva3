# ============================================================
# CLINICA/MODELS.PY / FICHA CLÍNICA DIGITAL
# La ficha (1 por mascota) se crea sola; las atenciones son el registro
# clínico: NO se borran (PROTECT y sin acción de eliminar en ninguna capa).
# ============================================================
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.archivos import almacenamiento_privado
from core.validadores import validar_adjunto_examen


class FichaClinica(models.Model):
    # CASCADE solo cae si la mascota se borra, y eso solo se permite sin historial
    # (las atenciones apuntan a la ficha con PROTECT y lo impedirían).
    mascota = models.OneToOneField("clientes.Mascota", on_delete=models.CASCADE, related_name="ficha")
    alergias = models.TextField(blank=True)
    antecedentes = models.TextField("antecedentes médicos", blank=True)
    observaciones = models.TextField(blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ficha clínica"
        verbose_name_plural = "fichas clínicas"
        ordering = ["mascota__nombre"]

    def __str__(self):
        return f"Ficha de {self.mascota.nombre}"


class Atencion(models.Model):
    ficha = models.ForeignKey(FichaClinica, on_delete=models.PROTECT, related_name="atenciones")
    # OneToOne opcional: una atención sin cita es una urgencia (atención "de mesón").
    cita = models.OneToOneField("agenda.Cita", on_delete=models.PROTECT, null=True, blank=True, related_name="atencion")
    veterinario = models.ForeignKey("agenda.Profesional", on_delete=models.PROTECT, related_name="atenciones")
    fecha = models.DateTimeField(default=timezone.now, db_index=True)
    anamnesis = models.TextField(help_text="Motivo y antecedentes que relata el tutor.")
    peso_kg = models.DecimalField(
        "peso registrado (kg)", max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    temperatura_c = models.DecimalField(
        "temperatura (°C)", max_digits=4, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(Decimal("30")), MaxValueValidator(Decimal("45"))],
    )
    diagnostico = models.TextField("diagnóstico")
    tratamiento = models.TextField(blank=True)
    observaciones = models.TextField(blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "atención"
        verbose_name_plural = "atenciones"
        ordering = ["-fecha"]
        constraints = [
            models.CheckConstraint(
                condition=Q(peso_kg__isnull=True) | Q(peso_kg__gt=0), name="atencion_peso_positivo"
            ),
            models.CheckConstraint(
                condition=Q(temperatura_c__isnull=True) | (Q(temperatura_c__gte=30) & Q(temperatura_c__lte=45)),
                name="atencion_temperatura_plausible",
                violation_error_message="La temperatura debe estar entre 30 °C y 45 °C.",
            ),
        ]

    def __str__(self):
        return f"Atención de {self.ficha.mascota.nombre} · {timezone.localtime(self.fecha):%d/%m/%Y}"


class Receta(models.Model):
    atencion = models.ForeignKey(Atencion, on_delete=models.PROTECT, related_name="recetas")
    medicamento = models.CharField(max_length=120)
    dosis = models.CharField(max_length=80)
    frecuencia = models.CharField(max_length=80)
    duracion = models.CharField(max_length=80)
    indicaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "receta"
        verbose_name_plural = "recetas"
        ordering = ["id"]

    def __str__(self):
        return f"{self.medicamento} ({self.dosis})"


class Examen(models.Model):
    atencion = models.ForeignKey(Atencion, on_delete=models.PROTECT, related_name="examenes")
    tipo = models.CharField(max_length=100)
    fecha = models.DateField(default=timezone.localdate)
    resultado = models.TextField(blank=True)
    # Privado: se guarda fuera de static y solo se entrega por una vista con permisos.
    archivo = models.FileField(
        upload_to="examenes/", storage=almacenamiento_privado, null=True, blank=True,
        validators=[validar_adjunto_examen],
        help_text="PDF, JPG o PNG de hasta 5 MB.",
    )

    class Meta:
        verbose_name = "examen"
        verbose_name_plural = "exámenes"
        ordering = ["-fecha", "id"]

    def __str__(self):
        return f"{self.tipo} ({self.fecha:%d/%m/%Y})"
