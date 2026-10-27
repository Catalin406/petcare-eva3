# ============================================================
# CLIENTES/MODELS.PY / TUTORES Y MASCOTAS
# Tutor: persona responsable, ligada a un Usuario con rol TUTOR (una
# sola fuente de verdad para nombre y correo). Mascota: pertenece a
# un tutor; si tiene historial clínico NO se borra, se desactiva.
# ============================================================

from decimal import Decimal

from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from core.archivos import almacenamiento_privado
from core.validadores import normalizar_rut, validar_foto, validar_no_futura, validar_rut


class RutField(models.CharField):
    """CharField que guarda el RUT normalizado ('12345678-5') y valida el dígito verificador."""

    default_validators = [validar_rut]

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 10)
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        valor = super().to_python(value)
        return normalizar_rut(valor) if valor else valor

    def get_prep_value(self, value):
        valor = super().get_prep_value(value)
        return normalizar_rut(valor) if valor else valor


class Tutor(models.Model):
    # PROTECT: borrar el usuario por accidente no debe dejar un tutor huérfano
    # ni arrastrar sus mascotas; el servicio decide qué se puede borrar.
    usuario = models.OneToOneField(
        "usuarios.Usuario",
        on_delete=models.PROTECT,
        related_name="tutor",
        limit_choices_to={"rol": "TUTOR"},
    )
    rut = RutField("RUT", unique=True, help_text="Con o sin puntos y guion. Ej.: 12.345.678-5")
    telefono = models.CharField(
        "teléfono",
        max_length=16,
        validators=[RegexValidator(r"^\+?[0-9 ]{8,15}$", "Ingresa un teléfono válido (8 a 15 dígitos, puede llevar +).")],
    )
    direccion = models.CharField("dirección", max_length=200)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "tutor"
        verbose_name_plural = "tutores"
        ordering = ["usuario__last_name", "usuario__first_name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rut__regex=r"^[0-9]{7,8}-[0-9K]$"),
                name="tutor_rut_formato_valido",
                violation_error_message="El RUT debe estar normalizado (ej.: 12345678-5).",
            ),
        ]

    def __str__(self):
        return f"{self.nombre_completo} ({self.rut})"

    @property
    def nombre_completo(self):
        return self.usuario.nombre_visible

    @property
    def email(self):
        # Única fuente de verdad: el correo vive en el Usuario.
        return self.usuario.email

    def save(self, *args, **kwargs):
        self.rut = normalizar_rut(self.rut)
        super().save(*args, **kwargs)


class Especie(models.TextChoices):
    PERRO = "PERRO", "Perro"
    GATO = "GATO", "Gato"
    AVE = "AVE", "Ave"
    CONEJO = "CONEJO", "Conejo"
    ROEDOR = "ROEDOR", "Roedor"
    REPTIL = "REPTIL", "Reptil"
    OTRO = "OTRO", "Otro"


class Sexo(models.TextChoices):
    MACHO = "MACHO", "Macho"
    HEMBRA = "HEMBRA", "Hembra"
    DESCONOCIDO = "DESCONOCIDO", "Desconocido"


class Mascota(models.Model):
    # PROTECT: un tutor con mascotas no se puede borrar de golpe.
    tutor = models.ForeignKey(Tutor, on_delete=models.PROTECT, related_name="mascotas")
    nombre = models.CharField(max_length=60)
    especie = models.CharField(max_length=10, choices=Especie.choices, db_index=True)
    raza = models.CharField(max_length=60, blank=True)
    sexo = models.CharField(max_length=12, choices=Sexo.choices, default=Sexo.DESCONOCIDO)
    fecha_nacimiento = models.DateField("fecha de nacimiento", validators=[validar_no_futura])
    peso = models.DecimalField(
        "peso (kg)", max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0.01"))]
    )
    color_senas = models.CharField("color / señas particulares", max_length=120, blank=True)
    # null (no "") para que varias mascotas sin chip no choquen en la restricción única.
    microchip = models.CharField(max_length=15, null=True, blank=True, help_text="Opcional. 15 dígitos, único.")
    foto = models.ImageField(
        upload_to="mascotas/", storage=almacenamiento_privado, null=True, blank=True, validators=[validar_foto]
    )
    activa = models.BooleanField(default=True, db_index=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "mascota"
        verbose_name_plural = "mascotas"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["microchip"],
                condition=models.Q(microchip__isnull=False),
                name="mascota_microchip_unico",
                violation_error_message="Ya existe una mascota con ese microchip.",
            ),
            # Un tutor no repite el nombre de sus mascotas (evita confundir fichas).
            models.UniqueConstraint(
                Lower("nombre"),
                "tutor",
                name="mascota_nombre_unico_por_tutor",
                violation_error_message="Este tutor ya tiene una mascota con ese nombre.",
            ),
            models.CheckConstraint(
                condition=models.Q(peso__isnull=True) | models.Q(peso__gt=0),
                name="mascota_peso_positivo",
            ),
            models.CheckConstraint(
                condition=models.Q(microchip__isnull=True) | models.Q(microchip__regex=r"^[0-9]{15}$"),
                name="mascota_microchip_15_digitos",
                violation_error_message="El microchip debe tener exactamente 15 dígitos.",
            ),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.get_especie_display()})"

    @property
    def edad_texto(self):
        """Edad calculada a hoy, en lenguaje simple (no se guarda: cambiaría cada día)."""
        hoy = timezone.localdate()
        nac = self.fecha_nacimiento
        meses = (hoy.year - nac.year) * 12 + (hoy.month - nac.month) - (1 if hoy.day < nac.day else 0)
        meses = max(meses, 0)
        anios, resto = divmod(meses, 12)
        if anios == 0:
            return f"{resto} mes" + ("" if resto == 1 else "es")
        texto = f"{anios} año" + ("" if anios == 1 else "s")
        return texto + (f" y {resto} mes" + ("" if resto == 1 else "es") if resto else "")

    @property
    def edad_anios(self):
        hoy = timezone.localdate()
        nac = self.fecha_nacimiento
        return hoy.year - nac.year - ((hoy.month, hoy.day) < (nac.month, nac.day))
