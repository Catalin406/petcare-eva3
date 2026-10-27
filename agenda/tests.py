# ============================================================
# AGENDA/TESTS.PY / REGLAS DE AGENDAMIENTO, CONSTRAINTS Y PERMISOS
# ============================================================
from datetime import time, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.fabricas import CLAVE, crear_mascota, crear_profesional, crear_tutor, crear_usuario, fecha_futura, momento
from usuarios.models import Rol

from . import servicios
from .models import BloqueoAgenda, Cita, DisponibilidadSemanal, EstadoCita, HistorialCita


class _AgendaBase(TestCase):
    def setUp(self):
        self.prof = crear_profesional("vet1")
        self.prof2 = crear_profesional("vet2")
        self.tutor = crear_tutor("ana", "12345678")
        self.otro_tutor = crear_tutor("beto", "22222222")
        self.mascota = crear_mascota(self.tutor, "Firulais")
        self.mascota2 = crear_mascota(self.tutor, "Michi", "GATO")
        self.ajena = crear_mascota(self.otro_tutor, "Rex")
        self.recep = crear_usuario("recep", Rol.RECEPCIONISTA)
        self.admin = crear_usuario("admin", Rol.ADMINISTRADOR)
        self.dia = fecha_futura(10)

    def agendar(self, mascota=None, prof=None, hora="10:00", usuario=None, **extra):
        return servicios.crear_cita(
            mascota=mascota or self.mascota, profesional=prof or self.prof, inicio=momento(self.dia, hora),
            motivo=extra.pop("motivo", "Control"), creada_por=usuario or self.recep, **extra,
        )


class CrearCitaTests(_AgendaBase):
    def test_crea_cita_con_duracion_del_bloque_e_historial(self):
        cita = self.agendar()
        self.assertEqual(cita.estado, EstadoCita.PROGRAMADA)
        self.assertEqual(cita.fin - cita.inicio, timedelta(minutes=30))
        self.assertEqual(cita.historial.count(), 1)
        self.assertEqual(cita.historial.first().estado_nuevo, EstadoCita.PROGRAMADA)

    def test_rechaza_cita_en_el_pasado(self):
        with self.assertRaisesMessage(ValidationError, "pasado"):
            servicios.crear_cita(
                mascota=self.mascota, profesional=self.prof, inicio=timezone.now() - timedelta(hours=2),
                fin=timezone.now() - timedelta(hours=1), motivo="x", creada_por=self.recep,
            )

    def test_rechaza_cita_fuera_de_la_disponibilidad(self):
        for hora in ("08:00", "18:00", "20:00"):
            with self.subTest(hora=hora), self.assertRaisesMessage(ValidationError, "no atiende en ese horario"):
                self.agendar(hora=hora)

    def test_rechaza_cita_que_termina_despues_del_cierre(self):
        with self.assertRaisesMessage(ValidationError, "no atiende en ese horario"):
            self.agendar(hora="17:45", fin=momento(self.dia, "18:15"))

    def test_rechaza_dia_sin_disponibilidad(self):
        prof = crear_profesional("solo_lunes", todos_los_dias=False)
        DisponibilidadSemanal.objects.create(
            profesional=prof, dia_semana=0, hora_inicio=time(9), hora_fin=time(12), duracion_bloque_min=30
        )
        proximo_martes = self.dia + timedelta(days=(1 - self.dia.weekday()) % 7 or 7)
        with self.assertRaisesMessage(ValidationError, "no atiende"):
            servicios.crear_cita(
                mascota=self.mascota, profesional=prof, inicio=momento(proximo_martes, "10:00"), motivo="x",
                creada_por=self.recep,
            )

    def test_rechaza_cita_dentro_de_un_bloqueo(self):
        BloqueoAgenda.objects.create(
            profesional=self.prof, inicio=momento(self.dia, "00:00"), fin=momento(self.dia + timedelta(days=2), "00:00"),
            motivo="Vacaciones",
        )
        with self.assertRaisesMessage(ValidationError, "Vacaciones"):
            self.agendar()

    def test_rechaza_solape_del_mismo_profesional(self):
        self.agendar(self.mascota, hora="10:00")
        with self.assertRaisesMessage(ValidationError, "ya tiene una cita"):
            self.agendar(self.mascota2, hora="10:00")
        with self.assertRaisesMessage(ValidationError, "ya tiene una cita"):
            self.agendar(self.mascota2, hora="10:15", fin=momento(self.dia, "10:45"))

    def test_rechaza_solape_de_la_misma_mascota_con_otro_profesional(self):
        self.agendar(self.mascota, self.prof, "10:00")
        with self.assertRaisesMessage(ValidationError, "Firulais ya tiene una cita"):
            self.agendar(self.mascota, self.prof2, "10:00")

    def test_citas_consecutivas_no_se_consideran_solape(self):
        self.agendar(self.mascota, hora="10:00")
        self.agendar(self.mascota2, hora="10:30")  # empieza justo cuando termina la otra
        self.assertEqual(Cita.objects.count(), 2)

    def test_otro_profesional_puede_atender_a_la_misma_hora(self):
        self.agendar(self.mascota, self.prof, "10:00")
        self.agendar(self.mascota2, self.prof2, "10:00")
        self.assertEqual(Cita.objects.count(), 2)

    def test_cita_cancelada_libera_el_horario(self):
        cita = self.agendar(self.mascota, hora="10:00")
        servicios.cambiar_estado(cita, EstadoCita.CANCELADA, usuario=self.recep)
        nueva = self.agendar(self.mascota2, hora="10:00")
        self.assertEqual(nueva.estado, EstadoCita.PROGRAMADA)

    def test_atendida_y_no_asistio_siguen_ocupando_el_horario(self):
        cita = self.agendar(self.mascota, hora="10:00")
        # Se simula que el tiempo pasó: la cita ya ocurrió y se marcó "No asistió".
        servicios.cambiar_estado(cita, EstadoCita.NO_ASISTIO, usuario=self.recep, ahora=cita.fin + timedelta(minutes=1))
        with self.assertRaisesMessage(ValidationError, "ya tiene una cita"):
            self.agendar(self.mascota2, hora="10:00")

    def test_mascota_inactiva_no_puede_agendar(self):
        self.mascota.activa = False
        self.mascota.save()
        with self.assertRaisesMessage(ValidationError, "inactiva"):
            self.agendar()


class ConstraintPostgresTests(_AgendaBase):
    """Segunda capa: la base de datos rechaza el solape aunque se salte el servicio."""

    def _crear_directo(self, mascota, prof, desde, hasta, estado=EstadoCita.PROGRAMADA):
        return Cita.objects.create(
            mascota=mascota, profesional=prof, inicio=momento(self.dia, desde), fin=momento(self.dia, hasta),
            motivo="x", estado=estado,
        )

    def test_exclusion_por_profesional(self):
        self._crear_directo(self.mascota, self.prof, "10:00", "10:30")
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._crear_directo(self.mascota2, self.prof, "10:15", "10:45")

    def test_exclusion_por_mascota(self):
        self._crear_directo(self.mascota, self.prof, "10:00", "10:30")
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._crear_directo(self.mascota, self.prof2, "10:15", "10:45")

    def test_la_exclusion_ignora_citas_canceladas(self):
        self._crear_directo(self.mascota, self.prof, "10:00", "10:30", estado=EstadoCita.CANCELADA)
        self._crear_directo(self.mascota, self.prof, "10:00", "10:30")  # no falla
        self._crear_directo(self.mascota2, self.prof, "10:00", "10:30", estado=EstadoCita.CANCELADA)

    def test_rangos_contiguos_son_validos(self):
        self._crear_directo(self.mascota, self.prof, "10:00", "10:30")
        self._crear_directo(self.mascota, self.prof, "10:30", "11:00")

    def test_check_fin_posterior_a_inicio(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._crear_directo(self.mascota, self.prof, "11:00", "10:00")

    def test_el_servicio_traduce_la_carrera_a_mensaje_amable(self):
        """Si la validación no ve el choque (carrera), el IntegrityError se vuelve un mensaje claro."""
        self._crear_directo(self.mascota, self.prof, "10:00", "10:30")
        original = servicios._validar_horario
        servicios._validar_horario = lambda **kw: None  # simula que otra petición ganó la carrera
        try:
            with self.assertRaisesMessage(ValidationError, "acaba de ser ocupado"):
                self.agendar(self.mascota2, hora="10:00")
        finally:
            servicios._validar_horario = original
        self.assertEqual(Cita.objects.count(), 1)


class TransicionesTests(_AgendaBase):
    def setUp(self):
        super().setUp()
        self.cita = self.agendar()

    def test_programada_a_confirmada(self):
        cita = servicios.cambiar_estado(self.cita, EstadoCita.CONFIRMADA, usuario=self.recep, comentario="Llamó")
        self.assertEqual(cita.estado, EstadoCita.CONFIRMADA)
        ultimo = HistorialCita.objects.filter(cita=cita).last()
        self.assertEqual((ultimo.estado_anterior, ultimo.estado_nuevo, ultimo.comentario), ("PROGRAMADA", "CONFIRMADA", "Llamó"))

    def test_estados_finales_no_tienen_salida(self):
        servicios.cambiar_estado(self.cita, EstadoCita.CANCELADA, usuario=self.recep)
        for destino in (EstadoCita.CONFIRMADA, EstadoCita.PROGRAMADA, EstadoCita.CANCELADA, EstadoCita.NO_ASISTIO):
            with self.subTest(destino=destino), self.assertRaisesMessage(ValidationError, "Transición no permitida"):
                servicios.cambiar_estado(self.cita, destino, usuario=self.recep)

    def test_no_se_vuelve_a_programada(self):
        servicios.cambiar_estado(self.cita, EstadoCita.CONFIRMADA, usuario=self.recep)
        with self.assertRaisesMessage(ValidationError, "Transición no permitida"):
            servicios.cambiar_estado(self.cita, EstadoCita.PROGRAMADA, usuario=self.recep)

    def test_atendida_no_se_puede_forzar_a_mano(self):
        with self.assertRaisesMessage(ValidationError, "al registrar la atención"):
            servicios.cambiar_estado(self.cita, EstadoCita.ATENDIDA, usuario=self.admin)

    def test_no_asistio_solo_despues_de_la_hora(self):
        with self.assertRaisesMessage(ValidationError, "aún no ocurre"):
            servicios.cambiar_estado(self.cita, EstadoCita.NO_ASISTIO, usuario=self.recep)

    def test_diccionario_de_transiciones_completo(self):
        self.assertEqual(set(servicios.TRANSICIONES), set(EstadoCita))
        for final in (EstadoCita.ATENDIDA, EstadoCita.CANCELADA, EstadoCita.NO_ASISTIO):
            self.assertEqual(servicios.TRANSICIONES[final], set())


class ReglasDelTutorTests(_AgendaBase):
    def test_tutor_agenda_para_su_mascota_con_anticipacion(self):
        cita = self.agendar(usuario=self.tutor.usuario)
        self.assertEqual(cita.creada_por, self.tutor.usuario)

    def test_tutor_no_puede_agendar_a_mascota_ajena(self):
        with self.assertRaises(PermissionDenied):
            self.agendar(self.ajena, usuario=self.tutor.usuario)

    @override_settings(CITA_ANTICIPACION_MIN_HORAS=48)
    def test_anticipacion_minima_configurable(self):
        pronto = momento(timezone.localdate() + timedelta(days=1), "10:00")
        with self.assertRaisesMessage(ValidationError, "48 horas de anticipación"):
            servicios.crear_cita(mascota=self.mascota, profesional=self.prof, inicio=pronto, motivo="x",
                                 creada_por=self.tutor.usuario)
        # personal de recepción no tiene esa restricción
        servicios.crear_cita(mascota=self.mascota, profesional=self.prof, inicio=pronto, motivo="x", creada_por=self.recep)

    def test_tutor_cancela_con_anticipacion(self):
        cita = self.agendar(usuario=self.tutor.usuario)
        servicios.cambiar_estado(cita, EstadoCita.CANCELADA, usuario=self.tutor.usuario)
        cita.refresh_from_db()
        self.assertEqual(cita.estado, EstadoCita.CANCELADA)

    @override_settings(CITA_ANTICIPACION_MIN_HORAS=24)
    def test_tutor_no_cancela_sin_anticipacion(self):
        cita = self.agendar(usuario=self.recep)
        Cita.objects.filter(pk=cita.pk).update(inicio=timezone.now() + timedelta(hours=3),
                                               fin=timezone.now() + timedelta(hours=4))
        with self.assertRaisesMessage(ValidationError, "24 horas"):
            servicios.cambiar_estado(cita, EstadoCita.CANCELADA, usuario=self.tutor.usuario)

    def test_tutor_no_cancela_cita_ajena(self):
        cita = self.agendar(self.ajena, usuario=self.recep)
        with self.assertRaises(PermissionDenied):
            servicios.cambiar_estado(cita, EstadoCita.CANCELADA, usuario=self.tutor.usuario)

    def test_tutor_solo_puede_cancelar(self):
        cita = self.agendar(usuario=self.tutor.usuario)
        with self.assertRaises(PermissionDenied):
            servicios.cambiar_estado(cita, EstadoCita.CONFIRMADA, usuario=self.tutor.usuario)

    def test_veterinario_solo_gestiona_su_agenda(self):
        cita = self.agendar(prof=self.prof)
        with self.assertRaises(PermissionDenied):
            servicios.cambiar_estado(cita, EstadoCita.CONFIRMADA, usuario=self.prof2.usuario)
        servicios.cambiar_estado(cita, EstadoCita.CONFIRMADA, usuario=self.prof.usuario)


class HorariosLibresTests(_AgendaBase):
    def test_genera_bloques_segun_la_disponibilidad(self):
        libres = servicios.horarios_libres(self.prof, self.dia)
        self.assertEqual(len(libres), 18)  # 09:00-18:00 en bloques de 30 min
        self.assertEqual(timezone.localtime(libres[0].inicio).strftime("%H:%M"), "09:00")
        self.assertEqual(timezone.localtime(libres[-1].fin).strftime("%H:%M"), "18:00")

    def test_el_horario_ocupado_no_aparece_como_libre(self):
        self.agendar(hora="10:00")
        horas = [timezone.localtime(h.inicio).strftime("%H:%M") for h in servicios.horarios_libres(self.prof, self.dia)]
        self.assertNotIn("10:00", horas)
        self.assertIn("09:30", horas)
        self.assertIn("10:30", horas)
        ocupados = [h for h in servicios.horarios_del_dia(self.prof, self.dia) if h.estado == "OCUPADO"]
        self.assertEqual(len(ocupados), 1)

    def test_un_bloqueo_quita_los_horarios(self):
        BloqueoAgenda.objects.create(
            profesional=self.prof, inicio=momento(self.dia, "12:00"), fin=momento(self.dia, "14:00"), motivo="Almuerzo largo"
        )
        estados = {timezone.localtime(h.inicio).strftime("%H:%M"): h.estado for h in servicios.horarios_del_dia(self.prof, self.dia)}
        self.assertEqual(estados["12:00"], "BLOQUEADO")
        self.assertEqual(estados["13:30"], "BLOQUEADO")
        self.assertEqual(estados["14:00"], "LIBRE")

    def test_los_bloques_pasados_no_se_ofrecen(self):
        hoy = timezone.localdate()
        ahora = momento(hoy, "12:10")
        libres = servicios.horarios_libres(self.prof, hoy, ahora=ahora)
        self.assertTrue(all(h.inicio > ahora for h in libres))
        self.assertEqual(timezone.localtime(libres[0].inicio).strftime("%H:%M"), "12:30")

    def test_dia_sin_disponibilidad_no_tiene_horarios(self):
        prof = crear_profesional("sin_horario", todos_los_dias=False)
        self.assertEqual(servicios.horarios_libres(prof, self.dia), [])

    def test_cita_cancelada_no_ocupa_el_bloque(self):
        cita = self.agendar(hora="10:00")
        servicios.cambiar_estado(cita, EstadoCita.CANCELADA, usuario=self.recep)
        horas = [timezone.localtime(h.inicio).strftime("%H:%M") for h in servicios.horarios_libres(self.prof, self.dia)]
        self.assertIn("10:00", horas)

    def test_eventos_del_calendario_ocultan_detalle_a_quien_no_corresponde(self):
        self.agendar(self.mascota, hora="10:00")
        propios = servicios.eventos_calendario(self.tutor.usuario, self.prof, self.dia, self.dia)
        ajenos = servicios.eventos_calendario(self.otro_tutor.usuario, self.prof, self.dia, self.dia)
        ocupado = lambda lista: next(e for e in lista if e["estado"] == "OCUPADO")
        self.assertIn("Firulais", ocupado(propios)["title"])
        self.assertEqual(ocupado(ajenos)["title"], "Ocupado")
        self.assertIsNone(ocupado(ajenos)["cita_id"])


class DisponibilidadSemanalTests(_AgendaBase):
    def _bloque(self, ini, fin, dia=0, prof=None, minutos=30):
        return DisponibilidadSemanal(
            profesional=prof or self.prof2, dia_semana=dia, hora_inicio=ini, hora_fin=fin, duracion_bloque_min=minutos
        )

    def test_bloques_solapados_del_mismo_profesional_se_rechazan(self):
        prof = crear_profesional("nuevo", todos_los_dias=False)
        DisponibilidadSemanal.objects.create(profesional=prof, dia_semana=0, hora_inicio=time(9), hora_fin=time(13), duracion_bloque_min=30)
        for ini, fin in ((time(12), time(15)), (time(8), time(10)), (time(10), time(11)), (time(9), time(13))):
            with self.subTest(ini=ini, fin=fin), self.assertRaisesMessage(ValidationError, "se superpone"):
                servicios.validar_disponibilidad(self._bloque(ini, fin, prof=prof))

    def test_bloques_contiguos_o_de_otro_dia_o_profesional_son_validos(self):
        prof = crear_profesional("nuevo", todos_los_dias=False)
        DisponibilidadSemanal.objects.create(profesional=prof, dia_semana=0, hora_inicio=time(9), hora_fin=time(13), duracion_bloque_min=30)
        servicios.validar_disponibilidad(self._bloque(time(13), time(17), prof=prof))        # contiguo
        servicios.validar_disponibilidad(self._bloque(time(10), time(12), dia=1, prof=prof))  # otro día
        otro = crear_profesional("otro_prof", todos_los_dias=False)
        servicios.validar_disponibilidad(self._bloque(time(10), time(12), prof=otro))          # otro profesional

    def test_editar_un_bloque_no_choca_consigo_mismo(self):
        prof = crear_profesional("nuevo", todos_los_dias=False)
        bloque = DisponibilidadSemanal.objects.create(profesional=prof, dia_semana=2, hora_inicio=time(9), hora_fin=time(13), duracion_bloque_min=30)
        bloque.hora_fin = time(14)
        bloque.full_clean()
        bloque.save()

    def test_hora_fin_debe_ser_posterior(self):
        with self.assertRaisesMessage(ValidationError, "posterior"):
            servicios.validar_disponibilidad(self._bloque(time(12), time(10)))

    def test_duracion_mayor_que_la_franja(self):
        with self.assertRaisesMessage(ValidationError, "mayor que la franja"):
            servicios.validar_disponibilidad(self._bloque(time(9), time(9, 20), minutos=30))

    def test_restricciones_de_base_de_datos(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            DisponibilidadSemanal.objects.create(profesional=self.prof, dia_semana=0, hora_inicio=time(20), hora_fin=time(19), duracion_bloque_min=30)
        with self.assertRaises(IntegrityError), transaction.atomic():
            DisponibilidadSemanal.objects.create(profesional=self.prof, dia_semana=0, hora_inicio=time(8), hora_fin=time(8, 30), duracion_bloque_min=1)


class ReprogramarTests(_AgendaBase):
    def test_reprograma_a_otro_horario_libre(self):
        cita = self.agendar(hora="10:00")
        servicios.reprogramar_cita(cita, usuario=self.recep, inicio=momento(self.dia, "11:00"))
        cita.refresh_from_db()
        self.assertEqual(timezone.localtime(cita.inicio).strftime("%H:%M"), "11:00")

    def test_puede_reprogramar_sobre_su_propio_horario(self):
        cita = self.agendar(hora="10:00")
        servicios.reprogramar_cita(cita, usuario=self.recep, inicio=momento(self.dia, "10:15"), fin=momento(self.dia, "10:45"))

    def test_no_reprograma_encima_de_otra_cita(self):
        self.agendar(self.mascota2, hora="11:00")
        cita = self.agendar(self.mascota, hora="10:00")
        with self.assertRaisesMessage(ValidationError, "ya tiene una cita"):
            servicios.reprogramar_cita(cita, usuario=self.recep, inicio=momento(self.dia, "11:00"))

    def test_no_se_reprograma_una_cita_finalizada(self):
        cita = self.agendar()
        servicios.cambiar_estado(cita, EstadoCita.CANCELADA, usuario=self.recep)
        with self.assertRaisesMessage(ValidationError, "No se puede modificar"):
            servicios.reprogramar_cita(cita, usuario=self.recep, inicio=momento(self.dia, "12:00"))


class AgendaWebYApiTests(_AgendaBase):
    def entrar(self, usuario):
        self.client.logout()
        self.client.force_login(usuario)

    def _token(self, usuario):
        r = self.client.post("/api/auth/token/", {"username": usuario.username, "password": CLAVE}, content_type="application/json")
        return {"HTTP_AUTHORIZATION": f"Bearer {r.json()['access']}"}

    def test_tutor_ve_solo_sus_citas(self):
        mia = self.agendar(self.mascota, hora="10:00")
        ajena = self.agendar(self.ajena, hora="11:00")
        self.entrar(self.tutor.usuario)
        r = self.client.get(reverse("cita_lista"))
        self.assertContains(r, "Firulais")
        self.assertNotContains(r, "Rex")
        self.assertEqual(self.client.get(reverse("cita_detalle", args=[mia.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("cita_detalle", args=[ajena.pk])).status_code, 404)

    def test_veterinario_solo_ve_su_agenda(self):
        suya = self.agendar(prof=self.prof, hora="10:00")
        otra = self.agendar(self.mascota2, prof=self.prof2, hora="10:00")
        self.entrar(self.prof.usuario)
        self.assertEqual(self.client.get(reverse("cita_detalle", args=[suya.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("cita_detalle", args=[otra.pk])).status_code, 404)

    def test_recepcion_agenda_por_la_web(self):
        self.entrar(self.recep)
        r = self.client.post(reverse("cita_crear"), {
            "mascota": self.mascota.pk, "profesional": self.prof.pk, "fecha": self.dia.isoformat(),
            "hora": "10:00", "motivo": "Vacuna anual",
        })
        cita = Cita.objects.get()
        self.assertRedirects(r, reverse("cita_detalle", args=[cita.pk]))

    def test_formulario_muestra_el_error_de_solape(self):
        self.agendar(self.mascota2, hora="10:00")
        self.entrar(self.recep)
        r = self.client.post(reverse("cita_crear"), {
            "mascota": self.mascota.pk, "profesional": self.prof.pk, "fecha": self.dia.isoformat(),
            "hora": "10:00", "motivo": "x",
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "ya tiene una cita")
        self.assertEqual(Cita.objects.count(), 1)

    def test_tutor_no_puede_agendar_a_mascota_ajena_en_la_web(self):
        self.entrar(self.tutor.usuario)
        r = self.client.post(reverse("cita_crear"), {
            "mascota": self.ajena.pk, "profesional": self.prof.pk, "fecha": self.dia.isoformat(), "hora": "10:00", "motivo": "x",
        })
        self.assertEqual(r.status_code, 200)  # la mascota ni siquiera es una opción válida
        self.assertFalse(Cita.objects.exists())

    def test_tutor_cancela_su_cita_por_la_web(self):
        cita = self.agendar(usuario=self.tutor.usuario)
        self.entrar(self.tutor.usuario)
        self.client.post(reverse("cita_cambiar_estado", args=[cita.pk]), {"estado": "CANCELADA"})
        cita.refresh_from_db()
        self.assertEqual(cita.estado, EstadoCita.CANCELADA)

    def test_tutor_no_cambia_estado_de_cita_ajena_404(self):
        cita = self.agendar(self.ajena)
        self.entrar(self.tutor.usuario)
        r = self.client.post(reverse("cita_cambiar_estado", args=[cita.pk]), {"estado": "CANCELADA"})
        self.assertEqual(r.status_code, 404)

    def test_disponibilidad_solo_para_veterinario_y_admin(self):
        for usuario, esperado in ((self.recep, 403), (self.tutor.usuario, 403), (self.prof.usuario, 200), (self.admin, 200)):
            self.entrar(usuario)
            self.assertEqual(self.client.get(reverse("disponibilidad_lista")).status_code, esperado, usuario.rol)

    def test_veterinario_define_su_disponibilidad_y_el_solape_se_rechaza(self):
        prof = crear_profesional("nuevo_vet", todos_los_dias=False)
        self.entrar(prof.usuario)
        datos = {"dia_semana": 0, "hora_inicio": "09:00", "hora_fin": "13:00", "duracion_bloque_min": 30}
        r = self.client.post(reverse("disponibilidad_crear"), datos)
        self.assertRedirects(r, reverse("disponibilidad_lista"))
        self.assertEqual(DisponibilidadSemanal.objects.get(profesional=prof).hora_fin, time(13))
        r = self.client.post(reverse("disponibilidad_crear"), {**datos, "hora_inicio": "12:00", "hora_fin": "15:00"})
        self.assertContains(r, "se superpone")
        self.assertEqual(DisponibilidadSemanal.objects.filter(profesional=prof).count(), 1)

    def test_veterinario_no_edita_disponibilidad_ajena(self):
        bloque = DisponibilidadSemanal.objects.filter(profesional=self.prof2).first()
        self.entrar(self.prof.usuario)
        self.assertEqual(self.client.get(reverse("disponibilidad_editar", args=[bloque.pk])).status_code, 404)

    def test_calendario_carga_para_todos_los_roles(self):
        for usuario in (self.recep, self.tutor.usuario, self.prof.usuario, self.admin):
            self.entrar(usuario)
            self.assertEqual(self.client.get(reverse("calendario")).status_code, 200)

    # ---- API ----
    def test_api_horarios_y_eventos(self):
        self.agendar(hora="10:00")
        cab = self._token(self.tutor.usuario)
        r = self.client.get(f"/api/profesionales/{self.prof.pk}/horarios/?fecha={self.dia.isoformat()}", **cab)
        self.assertEqual(r.status_code, 200)
        por_hora = {b["hora_inicio"]: b["estado"] for b in r.json()}
        self.assertEqual(por_hora["10:00"], "OCUPADO")
        self.assertEqual(por_hora["10:30"], "LIBRE")
        r = self.client.get(f"/api/agenda/eventos/?profesional={self.prof.pk}&start={self.dia}&end={self.dia + timedelta(days=1)}", **cab)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any(e["estado"] == "LIBRE" for e in r.json()))

    def test_api_fecha_invalida_da_400(self):
        r = self.client.get(f"/api/profesionales/{self.prof.pk}/horarios/?fecha=hoy", **self._token(self.recep))
        self.assertEqual(r.status_code, 400)

    def test_api_crea_cita_y_rechaza_solape_con_400(self):
        cab = self._token(self.recep)
        cuerpo = {"mascota": self.mascota.pk, "profesional": self.prof.pk, "inicio": momento(self.dia, "10:00").isoformat(), "motivo": "Control"}
        r = self.client.post("/api/citas/", cuerpo, content_type="application/json", **cab)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["estado"], "PROGRAMADA")
        r = self.client.post("/api/citas/", {**cuerpo, "mascota": self.mascota2.pk}, content_type="application/json", **cab)
        self.assertEqual(r.status_code, 400)
        self.assertIn("ya tiene una cita", str(r.json()))

    def test_api_cita_en_el_pasado_da_400(self):
        cuerpo = {"mascota": self.mascota.pk, "profesional": self.prof.pk,
                  "inicio": (timezone.now() - timedelta(days=1)).isoformat(), "motivo": "x"}
        r = self.client.post("/api/citas/", cuerpo, content_type="application/json", **self._token(self.recep))
        self.assertEqual(r.status_code, 400)
        self.assertIn("pasado", str(r.json()))

    def test_api_tutor_crea_y_cancela_solo_lo_suyo(self):
        cab = self._token(self.tutor.usuario)
        cuerpo = {"mascota": self.mascota.pk, "profesional": self.prof.pk, "inicio": momento(self.dia, "11:00").isoformat(), "motivo": "Vacuna"}
        r = self.client.post("/api/citas/", cuerpo, content_type="application/json", **cab)
        self.assertEqual(r.status_code, 201, r.content)
        cita_id = r.json()["id"]
        r = self.client.post("/api/citas/", {**cuerpo, "mascota": self.ajena.pk}, content_type="application/json", **cab)
        self.assertEqual(r.status_code, 400)  # la mascota ajena "no existe" para este tutor
        self.assertEqual(self.client.post(f"/api/citas/{cita_id}/cancelar/", **cab).status_code, 200)
        self.assertEqual(Cita.objects.get(pk=cita_id).estado, EstadoCita.CANCELADA)
        # no puede modificar ni borrar
        self.assertEqual(self.client.patch(f"/api/citas/{cita_id}/", {"motivo": "x"}, content_type="application/json", **cab).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/citas/{cita_id}/", **cab).status_code, 403)

    def test_api_tutor_no_ve_citas_ajenas(self):
        ajena = self.agendar(self.ajena, hora="10:00")
        cab = self._token(self.tutor.usuario)
        self.assertEqual(self.client.get(f"/api/citas/{ajena.pk}/", **cab).status_code, 404)
        self.assertEqual(self.client.get("/api/citas/", **cab).json()["count"], 0)
        self.assertEqual(self.client.post(f"/api/citas/{ajena.pk}/cancelar/", **cab).status_code, 404)

    def test_api_transicion_invalida_da_400(self):
        cita = self.agendar()
        cab = self._token(self.recep)
        self.client.post(f"/api/citas/{cita.pk}/cancelar/", **cab)
        r = self.client.post(f"/api/citas/{cita.pk}/cambiar-estado/", {"estado": "CONFIRMADA"}, content_type="application/json", **cab)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Transición no permitida", str(r.json()))

    def test_api_historial_de_la_cita(self):
        cita = self.agendar()
        cab = self._token(self.recep)
        self.client.post(f"/api/citas/{cita.pk}/cambiar-estado/", {"estado": "CONFIRMADA"}, content_type="application/json", **cab)
        r = self.client.get(f"/api/citas/{cita.pk}/historial/", **cab)
        self.assertEqual([h["estado_nuevo"] for h in r.json()], ["PROGRAMADA", "CONFIRMADA"])

    def test_api_veterinario_gestiona_su_disponibilidad(self):
        prof = crear_profesional("api_vet", todos_los_dias=False)
        cab = self._token(prof.usuario)
        cuerpo = {"dia_semana": 1, "hora_inicio": "09:00:00", "hora_fin": "12:00:00", "duracion_bloque_min": 20}
        r = self.client.post("/api/disponibilidades/", cuerpo, content_type="application/json", **cab)
        self.assertEqual(r.status_code, 201, r.content)
        r = self.client.post("/api/disponibilidades/", {**cuerpo, "hora_inicio": "11:00:00", "hora_fin": "14:00:00"}, content_type="application/json", **cab)
        self.assertEqual(r.status_code, 400)
        self.assertIn("superpone", str(r.json()))
        # un veterinario no ve los bloques de otro
        self.assertEqual(self.client.get("/api/disponibilidades/", **cab).json()["count"], 1)

    def test_api_tutor_no_accede_a_disponibilidades(self):
        self.assertEqual(self.client.get("/api/disponibilidades/", **self._token(self.tutor.usuario)).status_code, 403)

    def test_api_solo_admin_crea_profesionales(self):
        usuario = crear_usuario("nuevo_vet2", Rol.VETERINARIO)
        cuerpo = {"usuario": usuario.pk, "especialidad": "Cirugía"}
        self.assertEqual(self.client.post("/api/profesionales/", cuerpo, content_type="application/json", **self._token(self.recep)).status_code, 403)
        self.assertEqual(self.client.post("/api/profesionales/", cuerpo, content_type="application/json", **self._token(self.admin)).status_code, 201)
