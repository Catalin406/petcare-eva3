# ============================================================
# CLINICA/SERVICIOS.PY / REGLAS DE LA FICHA CLÍNICA
# Registrar una atención es una operación atómica: la atención, sus
# recetas, sus exámenes y el paso de la cita a ATENDIDA se guardan
# juntos o no se guarda nada.
# ============================================================
from datetime import datetime, time

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from agenda import servicios as servicios_agenda
from agenda.models import Cita, EstadoCita, Profesional
from usuarios.models import Rol

from .models import Atencion, Examen, FichaClinica, Receta

# Quién puede LEER información clínica. Recepción queda fuera a propósito:
# gestiona agenda y datos de contacto, no diagnósticos.
ROLES_CLINICOS = (Rol.ADMINISTRADOR, Rol.VETERINARIO, Rol.TUTOR)


# ------------------------------------------------------------
# ACCESO A NIVEL DE OBJETO
# ------------------------------------------------------------
def fichas_visibles(usuario):
    base = FichaClinica.objects.select_related("mascota", "mascota__tutor", "mascota__tutor__usuario")
    if usuario.rol in (Rol.ADMINISTRADOR, Rol.VETERINARIO):
        return base
    if usuario.rol == Rol.TUTOR:
        return base.filter(mascota__tutor__usuario=usuario)
    return base.none()


def atenciones_visibles(usuario):
    base = Atencion.objects.select_related("ficha__mascota__tutor__usuario", "veterinario__usuario", "cita")
    if usuario.rol in (Rol.ADMINISTRADOR, Rol.VETERINARIO):
        return base
    if usuario.rol == Rol.TUTOR:
        return base.filter(ficha__mascota__tutor__usuario=usuario)
    return base.none()


def recetas_visibles(usuario):
    return Receta.objects.select_related("atencion__ficha__mascota").filter(
        atencion__in=atenciones_visibles(usuario).values("pk")
    )


def examenes_visibles(usuario):
    return Examen.objects.select_related("atencion__ficha__mascota").filter(
        atencion__in=atenciones_visibles(usuario).values("pk")
    )


# ------------------------------------------------------------
# FICHA
# ------------------------------------------------------------
def actualizar_ficha(ficha, *, usuario, alergias, antecedentes, observaciones):
    if usuario.rol not in (Rol.ADMINISTRADOR, Rol.VETERINARIO):
        raise PermissionDenied("Solo veterinarios y administradores editan la ficha clínica.")
    ficha.alergias, ficha.antecedentes, ficha.observaciones = alergias, antecedentes, observaciones
    ficha.save()
    return ficha


# ------------------------------------------------------------
# ATENCIONES
# ------------------------------------------------------------
def _crear_detalles(atencion, recetas, examenes):
    for datos in recetas:
        receta = Receta(atencion=atencion, **datos)
        receta.full_clean()
        receta.save()
    for datos in examenes:
        examen = Examen(atencion=atencion, **datos)
        examen.full_clean()
        examen.save()


@transaction.atomic
def registrar_atencion(*, veterinario, ficha, datos, cita=None, recetas=(), examenes=(), ahora=None):
    """
    Registra una atención. Con cita: debe ser del veterinario, de la misma mascota y
    estar PROGRAMADA o CONFIRMADA; pasa a ATENDIDA en esta misma transacción.
    Sin cita: urgencia (la atención nace sin cita asociada).
    """
    ahora = ahora or timezone.now()
    if not isinstance(veterinario, Profesional) or veterinario.usuario.rol != Rol.VETERINARIO:
        raise PermissionDenied("Solo un veterinario puede registrar atenciones.")
    ficha = FichaClinica.objects.select_for_update().select_related("mascota").get(pk=ficha.pk)
    if not ficha.mascota.activa:
        raise ValidationError("La mascota está inactiva: no se pueden registrar nuevas atenciones.")

    if cita is not None:
        cita = Cita.objects.select_for_update().select_related("mascota", "profesional").get(pk=cita.pk)
        if cita.mascota_id != ficha.mascota_id:
            raise ValidationError("La cita no corresponde a esta mascota.")
        if cita.profesional_id != veterinario.pk:
            raise PermissionDenied("Solo el veterinario de la cita puede registrar su atención.")
        if cita.estado not in (EstadoCita.PROGRAMADA, EstadoCita.CONFIRMADA):
            raise ValidationError(f"No se puede atender una cita {cita.get_estado_display().lower()}.")
        if Atencion.objects.filter(cita=cita).exists():
            raise ValidationError("Esta cita ya tiene una atención registrada.")

    atencion = Atencion(ficha=ficha, cita=cita, veterinario=veterinario, **datos)
    atencion.full_clean()
    atencion.save()
    _crear_detalles(atencion, recetas, examenes)

    if atencion.peso_kg is not None:
        # El peso medido en la consulta es el más reciente: actualiza el de la mascota.
        ficha.mascota.peso = atencion.peso_kg
        ficha.mascota.save(update_fields=["peso", "actualizada_en"])

    if cita is not None:
        servicios_agenda.cambiar_estado(
            cita, EstadoCita.ATENDIDA, usuario=veterinario.usuario, desde_atencion=True,
            comentario="Atención clínica registrada", ahora=ahora,
        )
    return atencion


@transaction.atomic
def actualizar_atencion(atencion, *, usuario, datos, recetas=(), examenes=()):
    """Solo el veterinario que la escribió corrige su atención; se pueden agregar recetas y exámenes."""
    if usuario.rol != Rol.VETERINARIO or atencion.veterinario.usuario_id != usuario.pk:
        raise PermissionDenied("Solo el veterinario que registró la atención puede modificarla.")
    for campo, valor in datos.items():
        setattr(atencion, campo, valor)
    atencion.full_clean()
    atencion.save()
    _crear_detalles(atencion, recetas, examenes)
    return atencion


# ------------------------------------------------------------
# LÍNEA DE TIEMPO DE LA FICHA
# ------------------------------------------------------------
def _inicio_del_dia(fecha):
    return timezone.make_aware(datetime.combine(fecha, time.min))


def linea_de_tiempo(mascota):
    """Atenciones, vacunas y controles de la mascota, del más reciente al más antiguo."""
    from vacunacion.models import ControlPeriodico, RegistroVacuna

    eventos = []
    for a in Atencion.objects.filter(ficha__mascota=mascota).select_related("veterinario__usuario").prefetch_related(
        "recetas", "examenes"
    ):
        eventos.append({"tipo": "atencion", "fecha": timezone.localtime(a.fecha), "objeto": a})
    for r in RegistroVacuna.objects.filter(mascota=mascota).select_related("vacuna", "veterinario__usuario"):
        eventos.append({"tipo": "vacuna", "fecha": _inicio_del_dia(r.fecha_aplicacion), "objeto": r})
    for c in ControlPeriodico.objects.filter(mascota=mascota, realizado=True):
        eventos.append({"tipo": "control", "fecha": _inicio_del_dia(c.fecha_programada), "objeto": c})
    return sorted(eventos, key=lambda e: e["fecha"], reverse=True)
