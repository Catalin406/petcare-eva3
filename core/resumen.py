# ============================================================
# CORE/RESUMEN.PY / DATOS DE LA PÁGINA DE INICIO SEGÚN EL ROL
# Cada rol ve un resumen distinto: el veterinario sus citas de hoy,
# recepción la agenda del día, el tutor lo suyo. Todo parte de los
# mismos querysets filtrados por usuario que usan las vistas.
# ============================================================
from datetime import datetime, time, timedelta

from django.utils import timezone

from usuarios.models import Rol


def _rango_de_hoy():
    inicio = timezone.make_aware(datetime.combine(timezone.localdate(), time.min))
    return inicio, inicio + timedelta(days=1)


def resumen_para(usuario):
    # Importaciones locales: este módulo lo carga core y las apps dependen de core.
    from agenda import servicios as servicios_agenda
    from agenda.models import EstadoCita
    from clientes import servicios as servicios_clientes
    from vacunacion import servicios as servicios_vacunacion

    desde, hasta = _rango_de_hoy()
    citas = servicios_agenda.citas_visibles(usuario)
    activas = citas.exclude(estado=EstadoCita.CANCELADA)
    citas_hoy = activas.filter(inicio__gte=desde, inicio__lt=hasta).order_by("inicio")
    panel = servicios_vacunacion.panel_recordatorios(usuario)
    urgentes = list(panel["vencidos"][:3]) + list(panel["semana"][:3])
    ahora = timezone.now()
    por_confirmar = citas.filter(estado=EstadoCita.PROGRAMADA, inicio__gte=ahora)

    tarjetas = []
    contexto = {"recordatorios_urgentes": urgentes}

    if usuario.rol == Rol.VETERINARIO:
        por_atender = citas_hoy.filter(estado__in=[EstadoCita.PROGRAMADA, EstadoCita.CONFIRMADA])
        from clinica.models import Atencion

        mes = timezone.localdate().replace(day=1)
        tarjetas = [
            ("Citas de hoy", citas_hoy.count(), "bi-calendar-day", "cita_lista", ""),
            ("Por atender hoy", por_atender.count(), "bi-clipboard2-pulse", "cita_lista", "cafe"),
            ("Atenciones este mes", Atencion.objects.filter(veterinario__usuario=usuario, fecha__date__gte=mes).count(),
             "bi-journal-medical", "mascota_lista", ""),
            ("Recordatorios vencidos", panel["vencidos"].count(), "bi-exclamation-octagon", "recordatorio_panel", "cafe"),
        ]
        contexto["titulo_lista"] = "Tu agenda de hoy"
        contexto["citas_hoy"] = citas_hoy[:12]
    elif usuario.rol == Rol.TUTOR:
        proximas = activas.filter(inicio__gte=ahora).order_by("inicio")
        tarjetas = [
            ("Mis mascotas", servicios_clientes.mascotas_visibles(usuario).filter(activa=True).count(), "bi-heart", "mascota_lista", ""),
            ("Próximas citas", proximas.count(), "bi-calendar-check", "cita_lista", "cafe"),
            ("Vencidos", panel["vencidos"].count(), "bi-exclamation-octagon", "recordatorio_panel", ""),
            ("Próximos 7 días", panel["semana"].count(), "bi-alarm", "recordatorio_panel", "cafe"),
        ]
        contexto["titulo_lista"] = "Tus próximas citas"
        contexto["citas_hoy"] = proximas[:6]
    else:  # ADMINISTRADOR y RECEPCIONISTA
        tarjetas = [
            ("Citas de hoy", citas_hoy.count(), "bi-calendar-day", "cita_lista", ""),
            ("Por confirmar", por_confirmar.count(), "bi-hourglass-split", "cita_lista", "cafe"),
            ("Mascotas activas", servicios_clientes.mascotas_visibles(usuario).filter(activa=True).count(), "bi-heart", "mascota_lista", ""),
            ("Recordatorios vencidos", panel["vencidos"].count(), "bi-exclamation-octagon", "recordatorio_panel", "cafe"),
        ]
        contexto["titulo_lista"] = "Agenda de hoy"
        contexto["citas_hoy"] = citas_hoy[:12]

    contexto["tarjetas"] = tarjetas
    return contexto


def contexto_mascota(usuario, mascota):
    """Qué botones y secciones ve cada rol en el detalle de una mascota."""
    from agenda import servicios as servicios_agenda
    from agenda.models import EstadoCita
    from vacunacion import servicios as servicios_vacunacion

    rol = usuario.rol
    proximas = (
        servicios_agenda.citas_visibles(usuario)
        .filter(mascota=mascota, inicio__gte=timezone.now())
        .exclude(estado=EstadoCita.CANCELADA)
        .order_by("inicio")[:5]
    )
    vacunas = servicios_vacunacion.registros_vacuna_visibles(usuario).filter(mascota=mascota).order_by("proxima_dosis")[:6]
    recordatorios = (
        servicios_vacunacion.recordatorios_visibles(usuario).filter(mascota=mascota)
        .exclude(estado="COMPLETADO").order_by("fecha_objetivo")[:6]
    )
    return {
        "puede_editar": rol in (Rol.ADMINISTRADOR, Rol.RECEPCIONISTA),
        "puede_ver_tutor": rol in (Rol.ADMINISTRADOR, Rol.RECEPCIONISTA),
        "puede_ver_ficha": rol in (Rol.ADMINISTRADOR, Rol.VETERINARIO, Rol.TUTOR),
        "puede_pedir_cita": rol in (Rol.ADMINISTRADOR, Rol.RECEPCIONISTA, Rol.TUTOR) and mascota.activa,
        "citas_proximas": proximas,
        "vacunas_aplicadas": vacunas,
        "recordatorios_mascota": recordatorios,
    }
