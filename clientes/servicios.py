# ============================================================
# CLIENTES/SERVICIOS.PY / LÓGICA DE NEGOCIO DE TUTORES Y MASCOTAS
# Las vistas, la API y el seed llaman a estas funciones: la regla
# vive en un solo lugar.
# ============================================================
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from usuarios.models import Rol, Usuario

from .models import Mascota, Tutor


# ------------------------------------------------------------
# ACCESO A NIVEL DE OBJETO
# Un tutor jamás ve datos de otro tutor: todas las vistas y la API
# parten de estos querysets, así un objeto ajeno simplemente "no existe".
# ------------------------------------------------------------
def tutores_visibles(usuario):
    if usuario.rol in (Rol.ADMINISTRADOR, Rol.RECEPCIONISTA):
        return Tutor.objects.select_related("usuario")
    if usuario.rol == Rol.TUTOR:
        return Tutor.objects.select_related("usuario").filter(usuario=usuario)
    return Tutor.objects.none()


def mascotas_visibles(usuario):
    base = Mascota.objects.select_related("tutor", "tutor__usuario")
    if usuario.rol in (Rol.ADMINISTRADOR, Rol.RECEPCIONISTA, Rol.VETERINARIO):
        return base
    if usuario.rol == Rol.TUTOR:
        return base.filter(tutor__usuario=usuario)
    return base.none()


# ------------------------------------------------------------
# TUTORES
# ------------------------------------------------------------
@transaction.atomic
def crear_tutor(*, username, first_name, last_name, email, password, rut, telefono, direccion):
    """Crea el Usuario (rol TUTOR) y su Tutor en una sola transacción."""
    if not email:
        raise ValidationError({"email": "El correo es obligatorio: se usa para los recordatorios."})
    usuario = Usuario(username=username, first_name=first_name, last_name=last_name, email=email, rol=Rol.TUTOR)
    validate_password(password, usuario)
    usuario.set_password(password)
    usuario.full_clean(exclude=["password"])
    usuario.save()
    tutor = Tutor(usuario=usuario, rut=rut, telefono=telefono, direccion=direccion)
    tutor.full_clean()
    tutor.save()
    return tutor


@transaction.atomic
def actualizar_tutor(tutor, *, first_name, last_name, email, rut, telefono, direccion):
    if not email:
        raise ValidationError({"email": "El correo es obligatorio: se usa para los recordatorios."})
    usuario = tutor.usuario
    usuario.first_name, usuario.last_name, usuario.email = first_name, last_name, email
    usuario.full_clean(exclude=["password"])
    usuario.save()
    tutor.rut, tutor.telefono, tutor.direccion = rut, telefono, direccion
    tutor.full_clean()
    tutor.save()
    return tutor


@transaction.atomic
def eliminar_o_desactivar_tutor(tutor):
    """
    Con mascotas no se borra: se desactiva su cuenta (y sus mascotas quedan
    intactas con su historial). Sin mascotas se elimina por completo.
    Devuelve "eliminado" o "desactivado".
    """
    if tutor.mascotas.exists():
        tutor.usuario.is_active = False
        tutor.usuario.save(update_fields=["is_active"])
        return "desactivado"
    usuario = tutor.usuario
    tutor.delete()
    usuario.delete()
    return "eliminado"


# ------------------------------------------------------------
# MASCOTAS
# ------------------------------------------------------------
def tiene_historial_clinico(mascota):
    """Historial = citas, atenciones o vacunas registradas."""
    from agenda.models import Cita
    from clinica.models import Atencion
    from vacunacion.models import RegistroVacuna

    return (
        Cita.objects.filter(mascota=mascota).exists()
        or Atencion.objects.filter(ficha__mascota=mascota).exists()
        or RegistroVacuna.objects.filter(mascota=mascota).exists()
    )


@transaction.atomic
def eliminar_o_desactivar_mascota(mascota):
    """
    No se elimina una mascota con historial clínico: se desactiva para
    conservar su ficha. Sin historial se borra (junto con su ficha vacía).
    Devuelve "eliminada" o "desactivada".
    """
    if tiene_historial_clinico(mascota):
        mascota.activa = False
        mascota.save(update_fields=["activa", "actualizada_en"])
        return "desactivada"
    mascota.delete()
    return "eliminada"
