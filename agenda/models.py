# ============================================================
# AGENDA/MODELS.PY / PROFESIONALES, DISPONIBILIDAD, BLOQUEOS Y CITAS
# Garantía anti-solapamiento en DOS capas:
#   1) servicios.py valida y explica el error en lenguaje claro;
#   2) la base de datos (ExclusionConstraint + tstzrange + btree_gist)
#      lo impide aunque dos peticiones lleguen al mismo tiempo.
# ============================================================
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeBoundary, RangeOperators
from django.db import models
from django.db.models import Func, Q


class TsTzRange(Func):
    """Rango [inicio, fin) de timestamps con zona horaria, calculado en la base de datos."""

    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


class Profesional(models.Model):
    # PROTECT: no se puede borrar un veterinario con citas o atenciones.
    usuario = models.OneToOneField(
        "usuarios.Usuario", on_delete=models.PROTECT, related_name="profesional",
        limit_choices_to={"rol": "VETERINARIO"},
    )
    especialidad = models.CharField(max_length=80, default="Medicina general")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "profesional"
        verbose_name_plural = "profesionales"
        ordering = ["usuario__last_name", "usuario__first_name"]

    def __str__(self):
        return f"{self.usuario.nombre_visible} · {self.especialidad}"

    @property
    def nombre(self):
        return self.usuario.nombre_visible


class DiaSemana(models.IntegerChoices):
    # Mismos números que datetime.weekday() (lunes = 0).
    LUNES = 0, "Lunes"
    MARTES = 1, "Martes"
    MIERCOLES = 2, "Miércoles"
    JUEVES = 3, "Jueves"
    VIERNES = 4, "Viernes"
    SABADO = 5, "Sábado"
    DOMINGO = 6, "Domingo"


class DisponibilidadSemanal(models.Model):
    """Franja semanal recurrente en que el profesional atiende. Se parte en bloques de N minutos."""

    profesional = models.ForeignKey(Profesional, on_delete=models.CASCADE, related_name="disponibilidades")
    dia_semana = models.PositiveSmallIntegerField("día de la semana", choices=DiaSemana.choices)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    duracion_bloque_min = models.PositiveSmallIntegerField("duración del bloque (min)", default=30)

    class Meta:
        verbose_name = "disponibilidad semanal"
        verbose_name_plural = "disponibilidades semanales"
        ordering = ["profesional", "dia_semana", "hora_inicio"]
        constraints = [
            models.CheckConstraint(
                condition=Q(hora_fin__gt=models.F("hora_inicio")),
                name="disponibilidad_fin_despues_de_inicio",
                violation_error_message="La hora de término debe ser posterior a la de inicio.",
            ),
            models.CheckConstraint(
                condition=Q(duracion_bloque_min__gte=5) & Q(duracion_bloque_min__lte=240),
                name="disponibilidad_duracion_razonable",
                violation_error_message="La duración del bloque debe estar entre 5 y 240 minutos.",
            ),
            models.CheckConstraint(
                condition=Q(dia_semana__gte=0) & Q(dia_semana__lte=6),
                name="disponibilidad_dia_valido",
            ),
            # El solape ENTRE bloques distintos se valida en servicios.py (decisión de diseño:
            # PostgreSQL no tiene un tipo de rango solo de horas y no usamos tipos propios).
            models.UniqueConstraint(
                fields=["profesional", "dia_semana", "hora_inicio"],
                name="disponibilidad_inicio_unico",
                violation_error_message="Ya existe un bloque que empieza a esa hora ese día.",
            ),
        ]

    def __str__(self):
        return f"{self.profesional.nombre} · {self.get_dia_semana_display()} {self.hora_inicio:%H:%M}-{self.hora_fin:%H:%M}"

    def clean(self):
        from . import servicios

        servicios.validar_disponibilidad(self)


class BloqueoAgenda(models.Model):
    """Periodo en que el profesional no atiende (vacaciones, feriado, congreso...)."""

    profesional = models.ForeignKey(Profesional, on_delete=models.CASCADE, related_name="bloqueos")
    inicio = models.DateTimeField()
    fin = models.DateTimeField()
    motivo = models.CharField(max_length=120)

    class Meta:
        verbose_name = "bloqueo de agenda"
        verbose_name_plural = "bloqueos de agenda"
        ordering = ["-inicio"]
        constraints = [
            models.CheckConstraint(
                condition=Q(fin__gt=models.F("inicio")),
                name="bloqueo_fin_despues_de_inicio",
                violation_error_message="El fin del bloqueo debe ser posterior a su inicio.",
            ),
        ]

    def __str__(self):
        return f"{self.profesional.nombre}: {self.motivo} ({self.inicio:%d/%m/%Y})"


class EstadoCita(models.TextChoices):
    PROGRAMADA = "PROGRAMADA", "Programada"
    CONFIRMADA = "CONFIRMADA", "Confirmada"
    ATENDIDA = "ATENDIDA", "Atendida"
    CANCELADA = "CANCELADA", "Cancelada"
    NO_ASISTIO = "NO_ASISTIO", "No asistió"


class Cita(models.Model):
    # PROTECT en mascota y profesional: una cita (y su historial) no se pierde
    # porque alguien borre al paciente o al veterinario.
    mascota = models.ForeignKey("clientes.Mascota", on_delete=models.PROTECT, related_name="citas")
    profesional = models.ForeignKey(Profesional, on_delete=models.PROTECT, related_name="citas")
    inicio = models.DateTimeField(db_index=True)
    fin = models.DateTimeField()
    motivo = models.CharField(max_length=200)
    estado = models.CharField(max_length=12, choices=EstadoCita.choices, default=EstadoCita.PROGRAMADA, db_index=True)
    # SET_NULL: si se borra la cuenta de quien la creó, la cita se conserva.
    creada_por = models.ForeignKey(
        "usuarios.Usuario", on_delete=models.SET_NULL, null=True, blank=True, related_name="citas_creadas"
    )
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "cita"
        verbose_name_plural = "citas"
        ordering = ["inicio"]
        constraints = [
            models.CheckConstraint(
                condition=Q(fin__gt=models.F("inicio")),
                name="cita_fin_despues_de_inicio",
                violation_error_message="La cita debe terminar después de empezar.",
            ),
            # Un profesional no puede tener dos citas activas que se pisen en el tiempo.
            # Las canceladas quedan fuera: liberan el horario.
            ExclusionConstraint(
                name="cita_sin_solape_profesional",
                expressions=[
                    (TsTzRange("inicio", "fin", RangeBoundary()), RangeOperators.OVERLAPS),
                    ("profesional", RangeOperators.EQUAL),
                ],
                condition=~Q(estado="CANCELADA"),
                violation_error_message="El profesional ya tiene una cita en ese horario.",
            ),
            # Una mascota tampoco puede estar en dos citas al mismo tiempo (ni con otro profesional).
            ExclusionConstraint(
                name="cita_sin_solape_mascota",
                expressions=[
                    (TsTzRange("inicio", "fin", RangeBoundary()), RangeOperators.OVERLAPS),
                    ("mascota", RangeOperators.EQUAL),
                ],
                condition=~Q(estado="CANCELADA"),
                violation_error_message="La mascota ya tiene una cita en ese horario.",
            ),
        ]
        indexes = [models.Index(fields=["profesional", "inicio"], name="cita_prof_inicio_idx")]

    def __str__(self):
        return f"{self.mascota.nombre} con {self.profesional.nombre} · {self.inicio:%d/%m/%Y %H:%M}"


class HistorialCita(models.Model):
    """Bitácora de cambios de estado: quién, cuándo y por qué. Solo se agrega, nunca se edita."""

    cita = models.ForeignKey(Cita, on_delete=models.CASCADE, related_name="historial")
    estado_anterior = models.CharField(max_length=12, blank=True)
    estado_nuevo = models.CharField(max_length=12, choices=EstadoCita.choices)
    usuario = models.ForeignKey("usuarios.Usuario", on_delete=models.SET_NULL, null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    comentario = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "cambio de estado de cita"
        verbose_name_plural = "historial de citas"
        ordering = ["fecha", "id"]

    def __str__(self):
        return f"{self.cita_id}: {self.estado_anterior or '—'} → {self.estado_nuevo}"
