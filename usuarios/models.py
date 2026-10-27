# ============================================================
# USUARIOS/MODELS.PY / USUARIO PERSONALIZADO CON ROL
# Un único modelo de usuario con campo "rol" (más simple y auditable
# que grupos sueltos). is_staff NO se edita a mano: se sincroniza en
# save() para que solo el ADMINISTRADOR entre al Django Admin.
# ============================================================
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models.functions import Lower


class Rol(models.TextChoices):
    ADMINISTRADOR = "ADMINISTRADOR", "Administrador"
    RECEPCIONISTA = "RECEPCIONISTA", "Recepcionista"
    VETERINARIO = "VETERINARIO", "Veterinario"
    TUTOR = "TUTOR", "Tutor"


class UsuarioManager(UserManager):
    """createsuperuser debe producir un ADMINISTRADOR, no un TUTOR."""

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("rol", Rol.ADMINISTRADOR)
        return super().create_superuser(username, email, password, **extra_fields)


class Usuario(AbstractUser):
    # Rol por defecto = el de menos privilegios (principio de mínimo privilegio).
    rol = models.CharField("rol", max_length=15, choices=Rol.choices, default=Rol.TUTOR, db_index=True)

    objects = UsuarioManager()

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        constraints = [
            # El correo es la única fuente de verdad para avisar al tutor
            # (recordatorios), por eso no puede repetirse. Se permite vacío
            # para cuentas internas que no reciben correos.
            models.UniqueConstraint(
                Lower("email"),
                condition=~models.Q(email=""),
                name="usuario_email_unico_ci",
                violation_error_message="Ya existe un usuario con ese correo.",
            ),
        ]

    def __str__(self):
        return f"{self.nombre_visible} ({self.get_rol_display()})"

    @property
    def nombre_visible(self):
        return self.get_full_name() or self.username

    # ---------- Atajos de rol (se usan en plantillas y permisos) ----------
    @property
    def es_administrador(self):
        return self.rol == Rol.ADMINISTRADOR

    @property
    def es_recepcionista(self):
        return self.rol == Rol.RECEPCIONISTA

    @property
    def es_veterinario(self):
        return self.rol == Rol.VETERINARIO

    @property
    def es_tutor(self):
        return self.rol == Rol.TUTOR

    def save(self, *args, **kwargs):
        # Un superusuario siempre es ADMINISTRADOR (si no, perdería acceso).
        if self.is_superuser:
            self.rol = Rol.ADMINISTRADOR
        # is_staff solo para ADMINISTRADOR: así el Admin queda cerrado al resto.
        self.is_staff = self.rol == Rol.ADMINISTRADOR
        # Si el llamador guarda solo algunos campos, los dos derivados
        # deben viajar igual o la sincronización se perdería.
        campos = kwargs.get("update_fields")
        if campos is not None:
            kwargs["update_fields"] = set(campos) | {"is_staff", "rol"}
        super().save(*args, **kwargs)
