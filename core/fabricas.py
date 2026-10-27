# ============================================================
# CORE/FABRICAS.PY / CREADORES DE DATOS PARA PRUEBAS Y SEED
# Funciones pequeñas que arman usuarios, tutores, mascotas y agenda
# con datos válidos, para no repetir código en cada prueba.
# ============================================================
from datetime import datetime, time, timedelta

from django.utils import timezone

from agenda.models import DisponibilidadSemanal, Profesional
from clientes import servicios as servicios_clientes
from clientes.models import Mascota
from core.validadores import calcular_dv
from usuarios.models import Rol, Usuario

CLAVE = "ClaveSegura#2026"


def rut_valido(cuerpo):
    """'12345678' -> '12345678-5' (con el dígito verificador correcto)."""
    cuerpo = str(cuerpo)
    return f"{cuerpo}-{calcular_dv(cuerpo)}"


def crear_usuario(username, rol, **extra):
    extra.setdefault("email", f"{username}@petcare.test")
    return Usuario.objects.create_user(username=username, password=CLAVE, rol=rol, **extra)


def crear_tutor(username="tutor1", cuerpo_rut="12345678", **extra):
    return servicios_clientes.crear_tutor(
        username=username, password=CLAVE, first_name=extra.get("first_name", username.capitalize()),
        last_name=extra.get("last_name", "Pérez"), email=extra.get("email", f"{username}@correo.test"),
        rut=rut_valido(cuerpo_rut), telefono="+56911112222", direccion="Av. Siempre Viva 123",
    )


def crear_mascota(tutor, nombre="Firulais", especie="PERRO", **extra):
    return Mascota.objects.create(
        tutor=tutor, nombre=nombre, especie=especie, sexo="MACHO",
        fecha_nacimiento=extra.pop("fecha_nacimiento", timezone.localdate() - timedelta(days=800)), **extra,
    )


def crear_profesional(username="vet1", todos_los_dias=True, hora_inicio=time(9, 0), hora_fin=time(18, 0), bloque=30):
    usuario = crear_usuario(username, Rol.VETERINARIO, first_name="Vet", last_name=username.capitalize())
    profesional = Profesional.objects.create(usuario=usuario, especialidad="Medicina general")
    if todos_los_dias:
        for dia in range(7):
            DisponibilidadSemanal.objects.create(
                profesional=profesional, dia_semana=dia, hora_inicio=hora_inicio, hora_fin=hora_fin,
                duracion_bloque_min=bloque,
            )
    return profesional


def fecha_futura(dias=7):
    return timezone.localdate() + timedelta(days=dias)


def momento(fecha, hora="10:00"):
    """Fecha + 'HH:MM' en la zona horaria de la clínica (aware)."""
    h, m = (int(x) for x in hora.split(":"))
    return timezone.make_aware(datetime.combine(fecha, time(h, m)))
