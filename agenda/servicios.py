# ============================================================
# AGENDA/SERVICIOS.PY / REGLAS DE NEGOCIO DEL AGENDAMIENTO
# Aquí vive TODA la lógica: vistas, API, admin y seed la reutilizan.
# Los errores son ValidationError con mensajes claros en español; la
# ExclusionConstraint de PostgreSQL es la segunda capa de defensa.
# ============================================================
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from clientes.models import Mascota
from usuarios.models import Rol

from .models import BloqueoAgenda, Cita, DisponibilidadSemanal, EstadoCita, HistorialCita, Profesional

# ------------------------------------------------------------
# TRANSICIONES DE ESTADO VÁLIDAS
# Los estados finales (ATENDIDA, CANCELADA, NO_ASISTIO) no tienen salida.
# ------------------------------------------------------------
TRANSICIONES = {
    EstadoCita.PROGRAMADA: {EstadoCita.CONFIRMADA, EstadoCita.ATENDIDA, EstadoCita.CANCELADA, EstadoCita.NO_ASISTIO},
    EstadoCita.CONFIRMADA: {EstadoCita.ATENDIDA, EstadoCita.CANCELADA, EstadoCita.NO_ASISTIO},
    EstadoCita.ATENDIDA: set(),
    EstadoCita.CANCELADA: set(),
    EstadoCita.NO_ASISTIO: set(),
}

# Una cita ATENDIDA o NO_ASISTIO sigue "ocupando" el horario: ya se usó.
# Solo CANCELADA libera el espacio (coincide con la ExclusionConstraint).
ESTADOS_ACTIVOS = (EstadoCita.PROGRAMADA, EstadoCita.CONFIRMADA, EstadoCita.ATENDIDA, EstadoCita.NO_ASISTIO)


# ------------------------------------------------------------
# ACCESO A NIVEL DE OBJETO
# ------------------------------------------------------------
def citas_visibles(usuario):
    base = Cita.objects.select_related("mascota", "mascota__tutor", "mascota__tutor__usuario", "profesional", "profesional__usuario")
    if usuario.rol in (Rol.ADMINISTRADOR, Rol.RECEPCIONISTA):
        return base
    if usuario.rol == Rol.VETERINARIO:
        return base.filter(profesional__usuario=usuario)
    if usuario.rol == Rol.TUTOR:
        return base.filter(mascota__tutor__usuario=usuario)
    return base.none()


# ------------------------------------------------------------
# DISPONIBILIDAD SEMANAL (validación de solapes entre bloques)
# ------------------------------------------------------------
def validar_disponibilidad(disp):
    """Un bloque semanal no puede pisar a otro del mismo profesional y día."""
    if disp.hora_inicio is None or disp.hora_fin is None or disp.profesional_id is None:
        return
    if disp.hora_fin <= disp.hora_inicio:
        raise ValidationError("La hora de término debe ser posterior a la de inicio.")
    minutos = (
        datetime.combine(datetime.min, disp.hora_fin) - datetime.combine(datetime.min, disp.hora_inicio)
    ).total_seconds() / 60
    if disp.duracion_bloque_min and disp.duracion_bloque_min > minutos:
        raise ValidationError("La duración del bloque es mayor que la franja horaria completa.")
    pisados = DisponibilidadSemanal.objects.filter(
        profesional_id=disp.profesional_id,
        dia_semana=disp.dia_semana,
        hora_inicio__lt=disp.hora_fin,
        hora_fin__gt=disp.hora_inicio,
    ).exclude(pk=disp.pk)
    otro = pisados.first()
    if otro:
        raise ValidationError(
            f"Este bloque se superpone con otro del mismo día ({otro.hora_inicio:%H:%M} a {otro.hora_fin:%H:%M})."
        )


# ------------------------------------------------------------
# HORARIOS LIBRES DE UN PROFESIONAL PARA UN DÍA
# ------------------------------------------------------------
@dataclass
class Horario:
    inicio: datetime
    fin: datetime
    estado: str  # LIBRE | OCUPADO | BLOQUEADO | PASADO
    cita: Cita | None = None
    bloqueo: BloqueoAgenda | None = None


def _local(fecha, hora):
    return timezone.make_aware(datetime.combine(fecha, hora))


def horarios_del_dia(profesional, fecha, *, ahora=None, excluir_cita=None):
    """
    Divide cada franja de disponibilidad del día en bloques y marca cada uno como
    LIBRE, OCUPADO (cita activa), BLOQUEADO (vacaciones/feriado) o PASADO.
    """
    ahora = ahora or timezone.now()
    franjas = DisponibilidadSemanal.objects.filter(profesional=profesional, dia_semana=fecha.weekday())
    inicio_dia = _local(fecha, datetime.min.time())
    fin_dia = inicio_dia + timedelta(days=1)
    citas = Cita.objects.filter(profesional=profesional, inicio__lt=fin_dia, fin__gt=inicio_dia).exclude(
        estado=EstadoCita.CANCELADA
    )
    if excluir_cita is not None:
        citas = citas.exclude(pk=excluir_cita.pk)
    citas = list(citas.select_related("mascota"))
    bloqueos = list(BloqueoAgenda.objects.filter(profesional=profesional, inicio__lt=fin_dia, fin__gt=inicio_dia))

    resultado = []
    for franja in franjas:
        paso = timedelta(minutes=franja.duracion_bloque_min)
        actual = _local(fecha, franja.hora_inicio)
        limite = _local(fecha, franja.hora_fin)
        while actual + paso <= limite:
            fin = actual + paso
            horario = Horario(actual, fin, "LIBRE")
            bloqueo = next((b for b in bloqueos if b.inicio < fin and b.fin > actual), None)
            cita = next((c for c in citas if c.inicio < fin and c.fin > actual), None)
            if actual <= ahora:
                horario.estado = "PASADO"
            elif bloqueo:
                horario.estado, horario.bloqueo = "BLOQUEADO", bloqueo
            elif cita:
                horario.estado, horario.cita = "OCUPADO", cita
            resultado.append(horario)
            actual = fin
    return sorted(resultado, key=lambda h: h.inicio)


def horarios_libres(profesional, fecha, *, ahora=None, excluir_cita=None):
    """Solo los bloques que se pueden reservar."""
    return [h for h in horarios_del_dia(profesional, fecha, ahora=ahora, excluir_cita=excluir_cita) if h.estado == "LIBRE"]


# ------------------------------------------------------------
# VALIDACIÓN DE UN HORARIO PARA UNA CITA
# ------------------------------------------------------------
def _validar_horario(*, mascota, profesional, inicio, fin, ahora, excluir=None):
    if fin <= inicio:
        raise ValidationError("La cita debe terminar después de empezar.")
    if inicio <= ahora:
        raise ValidationError("No se pueden agendar citas en el pasado.")
    if not mascota.activa:
        raise ValidationError("La mascota está inactiva: no se pueden agendar citas.")
    if not profesional.activo or not profesional.usuario.is_active:
        raise ValidationError("El profesional no está disponible para atender.")

    # Debe caer COMPLETA dentro de una franja del profesional ese día.
    local_inicio, local_fin = timezone.localtime(inicio), timezone.localtime(fin)
    franjas = DisponibilidadSemanal.objects.filter(profesional=profesional, dia_semana=local_inicio.weekday())
    dentro = local_inicio.date() == local_fin.date() and any(
        f.hora_inicio <= local_inicio.time() and local_fin.time() <= f.hora_fin for f in franjas
    )
    if not dentro:
        raise ValidationError(
            f"{profesional.nombre} no atiende en ese horario "
            f"({local_inicio:%d/%m/%Y} de {local_inicio:%H:%M} a {local_fin:%H:%M}). Elige un horario dentro de su disponibilidad."
        )

    bloqueo = BloqueoAgenda.objects.filter(profesional=profesional, inicio__lt=fin, fin__gt=inicio).first()
    if bloqueo:
        raise ValidationError(f"{profesional.nombre} no atiende en esa fecha ({bloqueo.motivo}).")

    activas = Cita.objects.filter(inicio__lt=fin, fin__gt=inicio).exclude(estado=EstadoCita.CANCELADA)
    if excluir is not None:
        activas = activas.exclude(pk=excluir.pk)
    choque = activas.filter(profesional=profesional).first()
    if choque:
        raise ValidationError(
            f"{profesional.nombre} ya tiene una cita de {timezone.localtime(choque.inicio):%H:%M} "
            f"a {timezone.localtime(choque.fin):%H:%M} que se superpone con ese horario."
        )
    choque = activas.filter(mascota=mascota).first()
    if choque:
        raise ValidationError(
            f"{mascota.nombre} ya tiene una cita de {timezone.localtime(choque.inicio):%H:%M} "
            f"a {timezone.localtime(choque.fin):%H:%M} que se superpone con ese horario."
        )


def validar_cita(*, mascota, profesional, inicio, fin, excluir=None, ahora=None):
    """Valida un horario sin guardar (lo usa el Django Admin en su formulario)."""
    _validar_horario(
        mascota=mascota, profesional=profesional, inicio=inicio, fin=fin, ahora=ahora or timezone.now(), excluir=excluir
    )


def _duracion_del_bloque(profesional, inicio):
    """Si no se indica el término, la cita dura lo que dura el bloque donde empieza."""
    local = timezone.localtime(inicio)
    franja = DisponibilidadSemanal.objects.filter(
        profesional=profesional, dia_semana=local.weekday(), hora_inicio__lte=local.time(), hora_fin__gt=local.time()
    ).first()
    if franja is None:
        raise ValidationError(
            f"{profesional.nombre} no atiende en ese horario ({local:%d/%m/%Y %H:%M}). "
            "Elige un horario dentro de su disponibilidad."
        )
    return timedelta(minutes=franja.duracion_bloque_min)


def _validar_reglas_de_tutor(usuario, mascota, inicio, ahora):
    """El tutor solo agenda para SUS mascotas y con anticipación mínima configurable."""
    if mascota.tutor.usuario_id != usuario.pk:
        raise PermissionDenied("Un tutor solo puede agendar citas para sus propias mascotas.")
    minimo = timedelta(hours=settings.CITA_ANTICIPACION_MIN_HORAS)
    if inicio - ahora < minimo:
        raise ValidationError(
            f"Como tutor debes pedir la cita con al menos {settings.CITA_ANTICIPACION_MIN_HORAS} horas de anticipación. "
            "Para una atención más urgente, llama a recepción."
        )


def _registrar_historial(cita, anterior, nuevo, usuario, comentario=""):
    HistorialCita.objects.create(
        cita=cita, estado_anterior=anterior, estado_nuevo=nuevo, usuario=usuario, comentario=comentario
    )


# ------------------------------------------------------------
# CREAR / REPROGRAMAR
# ------------------------------------------------------------
@transaction.atomic
def crear_cita(*, mascota, profesional, inicio, motivo, creada_por, fin=None, ahora=None):
    """Agenda una cita validando todas las reglas. Devuelve la Cita creada."""
    ahora = ahora or timezone.now()
    if inicio <= ahora:  # primero: el mensaje más útil si además cae fuera de horario
        raise ValidationError("No se pueden agendar citas en el pasado.")
    # Se bloquean mascota y profesional (siempre en el mismo orden) para que dos
    # personas reservando a la vez se pongan en fila en vez de pisarse.
    mascota = Mascota.objects.select_for_update().select_related("tutor").get(pk=mascota.pk)
    profesional = Profesional.objects.select_for_update().select_related("usuario").get(pk=profesional.pk)
    if creada_por is not None and creada_por.rol == Rol.TUTOR:
        _validar_reglas_de_tutor(creada_por, mascota, inicio, ahora)
    fin = fin or inicio + _duracion_del_bloque(profesional, inicio)
    _validar_horario(mascota=mascota, profesional=profesional, inicio=inicio, fin=fin, ahora=ahora)
    try:
        # savepoint: si la BD rechaza la cita, la transacción externa sigue usable
        with transaction.atomic():
            cita = Cita.objects.create(
                mascota=mascota, profesional=profesional, inicio=inicio, fin=fin, motivo=motivo, creada_por=creada_por
            )
    except IntegrityError as error:
        # Segunda capa: la ExclusionConstraint atrapó una carrera que la validación no vio.
        raise ValidationError("Ese horario acaba de ser ocupado. Elige otro, por favor.") from error
    _registrar_historial(cita, "", cita.estado, creada_por, "Cita creada")
    return cita


@transaction.atomic
def reprogramar_cita(cita, *, usuario, inicio, profesional=None, motivo=None, fin=None, ahora=None):
    """Cambia fecha/hora (y opcionalmente profesional o motivo) de una cita PROGRAMADA o CONFIRMADA."""
    ahora = ahora or timezone.now()
    cita = Cita.objects.select_for_update().select_related("mascota", "mascota__tutor").get(pk=cita.pk)
    if cita.estado not in (EstadoCita.PROGRAMADA, EstadoCita.CONFIRMADA):
        raise ValidationError(f"No se puede modificar una cita {cita.get_estado_display().lower()}.")
    if usuario.rol == Rol.TUTOR:
        raise PermissionDenied("Un tutor no puede modificar citas: puede cancelarla y pedir otra.")
    if inicio <= ahora:
        raise ValidationError("No se pueden agendar citas en el pasado.")
    profesional = profesional or cita.profesional
    profesional = Profesional.objects.select_for_update().select_related("usuario").get(pk=profesional.pk)
    fin = fin or inicio + _duracion_del_bloque(profesional, inicio)
    _validar_horario(mascota=cita.mascota, profesional=profesional, inicio=inicio, fin=fin, ahora=ahora, excluir=cita)
    cita.profesional, cita.inicio, cita.fin = profesional, inicio, fin
    if motivo is not None:
        cita.motivo = motivo
    try:
        with transaction.atomic():
            cita.save()
    except IntegrityError as error:
        raise ValidationError("Ese horario acaba de ser ocupado. Elige otro, por favor.") from error
    _registrar_historial(cita, cita.estado, cita.estado, usuario, "Cita reprogramada")
    return cita


# ------------------------------------------------------------
# CAMBIO DE ESTADO
# ------------------------------------------------------------
@transaction.atomic
def cambiar_estado(cita, nuevo_estado, *, usuario, comentario="", desde_atencion=False, ahora=None):
    """
    Aplica una transición válida y deja constancia en el historial.
    ATENDIDA solo se alcanza al registrar la atención clínica (desde_atencion=True).
    """
    ahora = ahora or timezone.now()
    cita = Cita.objects.select_for_update().select_related("mascota", "mascota__tutor", "profesional").get(pk=cita.pk)
    nuevo_estado = EstadoCita(nuevo_estado)
    if nuevo_estado not in TRANSICIONES[EstadoCita(cita.estado)]:
        raise ValidationError(
            f"Transición no permitida: una cita {cita.get_estado_display().lower()} "
            f"no puede pasar a {nuevo_estado.label.lower()}."
        )
    if nuevo_estado == EstadoCita.ATENDIDA and not desde_atencion:
        raise ValidationError("Una cita pasa a «Atendida» al registrar la atención clínica, no manualmente.")
    if nuevo_estado == EstadoCita.NO_ASISTIO and cita.inicio > ahora:
        raise ValidationError("No se puede marcar «No asistió» una cita que aún no ocurre.")

    if usuario is not None and not desde_atencion:
        if usuario.rol == Rol.TUTOR:
            if cita.mascota.tutor.usuario_id != usuario.pk:
                raise PermissionDenied("Solo puedes gestionar las citas de tus mascotas.")
            if nuevo_estado != EstadoCita.CANCELADA:
                raise PermissionDenied("Un tutor solo puede cancelar sus citas.")
            if cita.inicio - ahora < timedelta(hours=settings.CITA_ANTICIPACION_MIN_HORAS):
                raise ValidationError(
                    f"Solo se puede cancelar con al menos {settings.CITA_ANTICIPACION_MIN_HORAS} horas de anticipación. "
                    "Comunícate con recepción."
                )
        elif usuario.rol == Rol.VETERINARIO:
            if cita.profesional.usuario_id != usuario.pk:
                raise PermissionDenied("Solo puedes gestionar tu propia agenda.")
            if nuevo_estado not in (EstadoCita.CONFIRMADA, EstadoCita.NO_ASISTIO):
                raise PermissionDenied("Un veterinario confirma citas o marca inasistencias; la cancelación la hace recepción.")

    anterior = cita.estado
    cita.estado = nuevo_estado
    cita.save(update_fields=["estado", "actualizada_en"])
    _registrar_historial(cita, anterior, nuevo_estado, usuario, comentario)
    return cita


# ------------------------------------------------------------
# EVENTOS PARA EL CALENDARIO (FullCalendar)
# ------------------------------------------------------------
def _puede_ver_detalle(usuario, cita):
    if usuario.rol in (Rol.ADMINISTRADOR, Rol.RECEPCIONISTA):
        return True
    if usuario.rol == Rol.VETERINARIO:
        return cita.profesional.usuario_id == usuario.pk
    return cita.mascota.tutor.usuario_id == usuario.pk


def eventos_calendario(usuario, profesional, desde, hasta, *, ahora=None):
    """
    Bloques del profesional entre dos fechas. A quien no le corresponde ver
    el detalle de una cita solo se le informa "Ocupado" (sin nombre de mascota).
    """
    eventos = []
    dia = desde
    while dia <= hasta:
        for h in horarios_del_dia(profesional, dia, ahora=ahora):
            evento = {
                "start": h.inicio.isoformat(),
                "end": h.fin.isoformat(),
                "estado": h.estado,
                "tipo": h.estado.lower(),
            }
            if h.estado == "OCUPADO":
                detalle = _puede_ver_detalle(usuario, h.cita)
                evento["title"] = f"{h.cita.mascota.nombre}: {h.cita.motivo}" if detalle else "Ocupado"
                evento["cita_id"] = h.cita.pk if detalle else None
                evento["estado_cita"] = h.cita.estado if detalle else None
            elif h.estado == "BLOQUEADO":
                evento["title"] = f"No atiende: {h.bloqueo.motivo}"
            elif h.estado == "LIBRE":
                evento["title"] = "Libre"
            else:
                evento["title"] = "—"
            eventos.append(evento)
        dia += timedelta(days=1)
    return eventos
