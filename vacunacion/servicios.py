# ============================================================
# VACUNACION/SERVICIOS.PY / VACUNAS, CONTROLES Y RECORDATORIOS
# generar_recordatorios es IDEMPOTENTE: correrlo dos veces seguidas no
# duplica avisos ni reenvía correos (get_or_create + enviado_en +
# restricciones únicas en la base de datos).
# ============================================================
import logging
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from agenda.models import Profesional
from usuarios.models import Rol

from .models import (
    CanalRecordatorio, ControlPeriodico, EstadoRecordatorio, Recordatorio, RegistroVacuna, TipoRecordatorio, Vacuna,
)

registro = logging.getLogger(__name__)


# ------------------------------------------------------------
# ACCESO A NIVEL DE OBJETO
# ------------------------------------------------------------
def _filtrar_por_rol(consulta, usuario, campo_tutor):
    if usuario.rol in (Rol.ADMINISTRADOR, Rol.RECEPCIONISTA, Rol.VETERINARIO):
        return consulta
    if usuario.rol == Rol.TUTOR:
        return consulta.filter(**{campo_tutor: usuario})
    return consulta.none()


def recordatorios_visibles(usuario):
    consulta = Recordatorio.objects.select_related(
        "mascota__tutor__usuario", "registro_vacuna__vacuna", "control"
    )
    return _filtrar_por_rol(consulta, usuario, "mascota__tutor__usuario")


def registros_vacuna_visibles(usuario):
    consulta = RegistroVacuna.objects.select_related("mascota__tutor__usuario", "vacuna", "veterinario__usuario")
    return _filtrar_por_rol(consulta, usuario, "mascota__tutor__usuario")


def controles_visibles(usuario):
    consulta = ControlPeriodico.objects.select_related("mascota__tutor__usuario")
    return _filtrar_por_rol(consulta, usuario, "mascota__tutor__usuario")


# ------------------------------------------------------------
# VACUNAS APLICADAS
# ------------------------------------------------------------
@transaction.atomic
def registrar_vacuna(*, mascota, vacuna, fecha_aplicacion, lote="", usuario=None):
    """Registra una aplicación; su próxima dosis se calcula sola (fecha + periodicidad)."""
    if usuario is not None and usuario.rol not in (Rol.ADMINISTRADOR, Rol.VETERINARIO):
        raise PermissionDenied("Solo veterinarios y administradores registran vacunas.")
    if not vacuna.activa:
        raise ValidationError({"vacuna": "Esa vacuna está desactivada en el catálogo."})
    if vacuna.especie_aplicable and vacuna.especie_aplicable != mascota.especie:
        raise ValidationError(
            {"vacuna": f"{vacuna.nombre} es para {vacuna.get_especie_aplicable_display().lower()}s, no para {mascota.get_especie_display().lower()}s."}
        )
    if not mascota.activa:
        raise ValidationError("La mascota está inactiva.")
    profesional = Profesional.objects.filter(usuario=usuario).first() if usuario else None
    nuevo = RegistroVacuna(
        mascota=mascota, vacuna=vacuna, fecha_aplicacion=fecha_aplicacion, lote=lote, veterinario=profesional
    )
    nuevo.proxima_dosis = nuevo.calcular_proxima_dosis()  # antes de validar: la columna no admite nulos
    nuevo.full_clean()
    nuevo.save()
    # La aplicación nueva "cierra" los avisos de las dosis anteriores de esa misma vacuna.
    Recordatorio.objects.filter(
        registro_vacuna__mascota=mascota, registro_vacuna__vacuna=vacuna, registro_vacuna__fecha_aplicacion__lt=fecha_aplicacion
    ).exclude(estado=EstadoRecordatorio.COMPLETADO).update(estado=EstadoRecordatorio.COMPLETADO)
    return nuevo


def marcar_control_realizado(control, *, realizado=True):
    control.realizado = realizado
    control.save(update_fields=["realizado"])
    if realizado:
        control.recordatorios.exclude(estado=EstadoRecordatorio.COMPLETADO).update(estado=EstadoRecordatorio.COMPLETADO)
    return control


# ------------------------------------------------------------
# GENERACIÓN DE RECORDATORIOS (comando generar_recordatorios)
# ------------------------------------------------------------
def _canal_para(mascota):
    return CanalRecordatorio.EMAIL if mascota.tutor.usuario.email else CanalRecordatorio.SISTEMA


def _completar_resueltos():
    """Cierra avisos cuyo origen ya se resolvió (vacuna más reciente aplicada, control realizado)."""
    mas_nueva = RegistroVacuna.objects.filter(
        mascota=OuterRef("registro_vacuna__mascota"),
        vacuna=OuterRef("registro_vacuna__vacuna"),
        fecha_aplicacion__gt=OuterRef("registro_vacuna__fecha_aplicacion"),
    )
    abiertos = Recordatorio.objects.exclude(estado=EstadoRecordatorio.COMPLETADO)
    n = abiertos.filter(tipo=TipoRecordatorio.VACUNA).filter(Exists(mas_nueva)).update(estado=EstadoRecordatorio.COMPLETADO)
    n += abiertos.filter(tipo=TipoRecordatorio.CONTROL, control__realizado=True).update(
        estado=EstadoRecordatorio.COMPLETADO
    )
    return n


def _correo_del_recordatorio(rec):
    mascota, tutor = rec.mascota, rec.mascota.tutor
    vencido = rec.estado == EstadoRecordatorio.VENCIDO
    asunto = f"PetCare: {'vencido' if vencido else 'recordatorio'} para {mascota.nombre}"
    cuando = (
        f"venció el {rec.fecha_objetivo:%d/%m/%Y}" if vencido else f"corresponde el {rec.fecha_objetivo:%d/%m/%Y}"
    )
    cuerpo = (
        f"Hola {tutor.usuario.first_name or tutor.nombre_completo},\n\n"
        f"Te recordamos que a {mascota.nombre} le {cuando}: {rec.descripcion}.\n"
        f"Puedes pedir una hora desde el sitio de {settings.NOMBRE_COMERCIAL} o llamando a recepción.\n\n"
        f"Equipo {settings.NOMBRE_COMERCIAL}"
    )
    return asunto, cuerpo


def generar_recordatorios(*, dias=None, hoy=None, enviar=True):
    """
    1) Cierra avisos ya resueltos. 2) Crea avisos para vacunas y controles que vencen
    dentro de `dias` (o ya vencieron). 3) Marca VENCIDO lo que pasó de fecha.
    4) Envía el correo al tutor (una sola vez por aviso). Devuelve un resumen.
    """
    dias = settings.DIAS_ANTICIPACION_RECORDATORIO if dias is None else dias
    hoy = hoy or timezone.localdate()
    limite = hoy + timedelta(days=dias)
    resumen = {"creados": 0, "vencidos": 0, "completados": 0, "enviados": 0, "sin_correo": 0, "errores_envio": 0}

    with transaction.atomic():
        resumen["completados"] = _completar_resueltos()

        # Solo cuenta la última aplicación de cada (mascota, vacuna): es la que define la próxima dosis.
        ultimas = (
            RegistroVacuna.objects.filter(mascota__activa=True, vacuna__activa=True)
            .select_related("mascota__tutor__usuario", "vacuna")
            .order_by("mascota_id", "vacuna_id", "-fecha_aplicacion")
            .distinct("mascota_id", "vacuna_id")
        )
        for r in ultimas:
            if r.proxima_dosis <= limite:
                _, creado = Recordatorio.objects.get_or_create(
                    registro_vacuna=r, fecha_objetivo=r.proxima_dosis,
                    defaults={"mascota": r.mascota, "tipo": TipoRecordatorio.VACUNA, "canal": _canal_para(r.mascota)},
                )
                resumen["creados"] += creado

        controles = ControlPeriodico.objects.filter(
            realizado=False, fecha_programada__lte=limite, mascota__activa=True
        ).select_related("mascota__tutor__usuario")
        for c in controles:
            _, creado = Recordatorio.objects.get_or_create(
                control=c, fecha_objetivo=c.fecha_programada,
                defaults={"mascota": c.mascota, "tipo": TipoRecordatorio.CONTROL, "canal": _canal_para(c.mascota)},
            )
            resumen["creados"] += creado

        resumen["vencidos"] = Recordatorio.objects.filter(
            estado__in=[EstadoRecordatorio.PENDIENTE, EstadoRecordatorio.ENVIADO], fecha_objetivo__lt=hoy
        ).update(estado=EstadoRecordatorio.VENCIDO)

    if enviar:
        por_enviar = Recordatorio.objects.filter(
            enviado_en__isnull=True, estado__in=[EstadoRecordatorio.PENDIENTE, EstadoRecordatorio.VENCIDO]
        ).select_related("mascota__tutor__usuario", "registro_vacuna__vacuna", "control")
        for rec in por_enviar:
            if rec.canal != CanalRecordatorio.EMAIL or not rec.mascota.tutor.usuario.email:
                resumen["sin_correo"] += 1
                continue
            asunto, cuerpo = _correo_del_recordatorio(rec)
            try:
                send_mail(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, [rec.mascota.tutor.usuario.email])
            except Exception:  # un correo caído no debe detener el resto ni dejar el aviso a medias
                registro.exception("No se pudo enviar el recordatorio %s", rec.pk)
                resumen["errores_envio"] += 1
                continue
            rec.enviado_en = timezone.now()
            if rec.estado == EstadoRecordatorio.PENDIENTE:
                rec.estado = EstadoRecordatorio.ENVIADO
            rec.save(update_fields=["enviado_en", "estado"])
            resumen["enviados"] += 1
    return resumen


# ------------------------------------------------------------
# PANEL WEB: VENCIDOS / PRÓXIMOS 7 DÍAS / PRÓXIMOS 30 DÍAS
# ------------------------------------------------------------
def panel_recordatorios(usuario, *, hoy=None):
    hoy = hoy or timezone.localdate()
    abiertos = recordatorios_visibles(usuario).exclude(estado=EstadoRecordatorio.COMPLETADO)
    return {
        "vencidos": abiertos.filter(fecha_objetivo__lt=hoy).order_by("fecha_objetivo"),
        "semana": abiertos.filter(fecha_objetivo__gte=hoy, fecha_objetivo__lte=hoy + timedelta(days=7)),
        "mes": abiertos.filter(
            fecha_objetivo__gt=hoy + timedelta(days=7), fecha_objetivo__lte=hoy + timedelta(days=30)
        ),
    }
