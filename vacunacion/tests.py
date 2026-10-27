# ============================================================
# VACUNACION/TESTS.PY / PRÓXIMA DOSIS, RECORDATORIOS IDEMPOTENTES Y PERMISOS
# ============================================================
from datetime import timedelta
from io import StringIO

from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.fabricas import CLAVE, crear_mascota, crear_profesional, crear_tutor, crear_usuario
from usuarios.models import Rol

from . import servicios
from .models import ControlPeriodico, EstadoRecordatorio, Recordatorio, RegistroVacuna, TipoRecordatorio, Vacuna


class _VacunacionBase(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.prof = crear_profesional("vet1")
        self.recep = crear_usuario("recep", Rol.RECEPCIONISTA)
        self.admin = crear_usuario("admin", Rol.ADMINISTRADOR)
        self.tutor = crear_tutor("ana", "12345678", email="ana@correo.test")
        self.otro_tutor = crear_tutor("beto", "22222222", email="beto@correo.test")
        self.mascota = crear_mascota(self.tutor, "Firulais")
        self.ajena = crear_mascota(self.otro_tutor, "Rex")
        self.rabia = Vacuna.objects.create(nombre="Rabia", periodicidad_dias=365)
        self.triple = Vacuna.objects.create(nombre="Triple felina", especie_aplicable="GATO", periodicidad_dias=180)

    def aplicar(self, mascota, vacuna, dias_atras):
        """Registra una vacuna aplicada hace `dias_atras` días (próxima dosis = esa fecha + periodicidad)."""
        return RegistroVacuna.objects.create(
            mascota=mascota, vacuna=vacuna, fecha_aplicacion=self.hoy - timedelta(days=dias_atras), veterinario=self.prof
        )

    def entrar(self, usuario):
        self.client.logout()
        self.client.force_login(usuario)


class ProximaDosisTests(_VacunacionBase):
    def test_se_calcula_sola_con_la_periodicidad(self):
        r = self.aplicar(self.mascota, self.rabia, 10)
        self.assertEqual(r.proxima_dosis, r.fecha_aplicacion + timedelta(days=365))

    def test_se_recalcula_si_cambia_la_fecha(self):
        r = self.aplicar(self.mascota, self.rabia, 10)
        r.fecha_aplicacion = self.hoy - timedelta(days=100)
        r.save()
        r.refresh_from_db()
        self.assertEqual(r.proxima_dosis, self.hoy - timedelta(days=100) + timedelta(days=365))

    def test_no_se_puede_fijar_a_mano(self):
        r = RegistroVacuna(mascota=self.mascota, vacuna=self.rabia, fecha_aplicacion=self.hoy, proxima_dosis=self.hoy)
        r.save()
        self.assertEqual(r.proxima_dosis, self.hoy + timedelta(days=365))

    def test_fecha_futura_de_aplicacion_rechazada(self):
        r = RegistroVacuna(mascota=self.mascota, vacuna=self.rabia, fecha_aplicacion=self.hoy + timedelta(days=2))
        r.proxima_dosis = r.calcular_proxima_dosis()
        with self.assertRaises(ValidationError):
            r.full_clean()

    def test_no_se_repite_la_misma_vacuna_el_mismo_dia(self):
        self.aplicar(self.mascota, self.rabia, 5)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.aplicar(self.mascota, self.rabia, 5)

    def test_periodicidad_debe_ser_positiva(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Vacuna.objects.create(nombre="Mala", periodicidad_dias=0)


class RegistrarVacunaServicioTests(_VacunacionBase):
    def test_veterinario_registra_y_queda_su_firma(self):
        r = servicios.registrar_vacuna(
            mascota=self.mascota, vacuna=self.rabia, fecha_aplicacion=self.hoy, lote="L-77", usuario=self.prof.usuario
        )
        self.assertEqual(r.veterinario, self.prof)
        self.assertEqual(r.proxima_dosis, self.hoy + timedelta(days=365))

    def test_especie_incompatible(self):
        with self.assertRaisesMessage(ValidationError, "es para gatos"):
            servicios.registrar_vacuna(mascota=self.mascota, vacuna=self.triple, fecha_aplicacion=self.hoy, usuario=self.prof.usuario)

    def test_recepcion_y_tutor_no_registran(self):
        for usuario in (self.recep, self.tutor.usuario):
            with self.assertRaises(PermissionDenied):
                servicios.registrar_vacuna(mascota=self.mascota, vacuna=self.rabia, fecha_aplicacion=self.hoy, usuario=usuario)

    def test_vacuna_desactivada_no_se_aplica(self):
        self.rabia.activa = False
        self.rabia.save()
        with self.assertRaises(ValidationError):
            servicios.registrar_vacuna(mascota=self.mascota, vacuna=self.rabia, fecha_aplicacion=self.hoy, usuario=self.prof.usuario)


class GenerarRecordatoriosTests(_VacunacionBase):
    def setUp(self):
        super().setUp()
        # próxima dosis: vencida hace 10 días / en 5 días / en 20 días / en 200 días (fuera de ventana)
        self.vencida = self.aplicar(self.mascota, self.rabia, 365 + 10)
        self.en_5 = self.aplicar(self.ajena, self.rabia, 365 - 5)
        self.en_20 = self.aplicar(self.mascota, Vacuna.objects.create(nombre="Tos de las perreras", periodicidad_dias=100), 80)
        self.lejana = self.aplicar(self.ajena, Vacuna.objects.create(nombre="Giardia", periodicidad_dias=365), 165)

    def test_crea_avisos_solo_dentro_de_la_ventana(self):
        r = servicios.generar_recordatorios(dias=30)
        self.assertEqual(r["creados"], 3)
        objetivos = set(Recordatorio.objects.values_list("registro_vacuna_id", flat=True))
        self.assertEqual(objetivos, {self.vencida.pk, self.en_5.pk, self.en_20.pk})
        self.assertNotIn(self.lejana.pk, objetivos)

    def test_marca_vencido_lo_que_paso_de_fecha(self):
        servicios.generar_recordatorios(dias=30)
        self.assertEqual(Recordatorio.objects.get(registro_vacuna=self.vencida).estado, EstadoRecordatorio.VENCIDO)
        self.assertEqual(Recordatorio.objects.get(registro_vacuna=self.en_5).estado, EstadoRecordatorio.ENVIADO)

    def test_es_idempotente(self):
        primera = servicios.generar_recordatorios(dias=30)
        correos_1, avisos_1 = len(mail.outbox), Recordatorio.objects.count()
        segunda = servicios.generar_recordatorios(dias=30)
        self.assertEqual(primera["creados"], 3)
        self.assertEqual((segunda["creados"], segunda["enviados"], segunda["vencidos"]), (0, 0, 0))
        self.assertEqual(Recordatorio.objects.count(), avisos_1)
        self.assertEqual(len(mail.outbox), correos_1)  # no se reenvían correos

    def test_comando_de_gestion_es_idempotente(self):
        salida = StringIO()
        call_command("generar_recordatorios", "--dias", "30", stdout=salida)
        self.assertIn("3 creados", salida.getvalue())
        total, correos = Recordatorio.objects.count(), len(mail.outbox)
        salida = StringIO()
        call_command("generar_recordatorios", "--dias", "30", stdout=salida)
        self.assertIn("0 creados", salida.getvalue())
        self.assertEqual((Recordatorio.objects.count(), len(mail.outbox)), (total, correos))

    @override_settings(DIAS_ANTICIPACION_RECORDATORIO=60)
    def test_los_dias_por_defecto_vienen_de_la_configuracion(self):
        # con 60 días entra también "en_20" y... la dosis de "lejana" sigue fuera (35 días de margen)
        r = servicios.generar_recordatorios()
        self.assertEqual(r["creados"], 3)
        r = servicios.generar_recordatorios(dias=200)
        self.assertEqual(r["creados"], 1)  # ahora sí entra "lejana"

    def test_envia_el_correo_al_tutor_con_el_email_del_usuario(self):
        servicios.generar_recordatorios(dias=30)
        destinatarios = sorted(d for m in mail.outbox for d in m.to)
        self.assertEqual(destinatarios, ["ana@correo.test", "ana@correo.test", "beto@correo.test"])
        vencido = next(m for m in mail.outbox if "vencido" in m.subject)
        self.assertIn("Rabia", vencido.body)
        self.assertIn("Firulais", vencido.body)

    def test_tutor_sin_correo_queda_solo_en_el_sistema(self):
        self.tutor.usuario.email = ""
        self.tutor.usuario.save()
        r = servicios.generar_recordatorios(dias=30)
        self.assertGreaterEqual(r["sin_correo"], 1)
        self.assertTrue(Recordatorio.objects.filter(mascota=self.mascota, canal="SISTEMA").exists())
        self.assertFalse(any(self.tutor.usuario.username in str(m.to) for m in mail.outbox))

    def test_sin_correo_flag(self):
        r = servicios.generar_recordatorios(dias=30, enviar=False)
        self.assertEqual(r["enviados"], 0)
        self.assertEqual(len(mail.outbox), 0)
        # y un envío posterior sí los manda
        self.assertEqual(servicios.generar_recordatorios(dias=30)["enviados"], 3)

    def test_nueva_aplicacion_cierra_el_aviso_anterior(self):
        servicios.generar_recordatorios(dias=30)
        servicios.registrar_vacuna(mascota=self.mascota, vacuna=self.rabia, fecha_aplicacion=self.hoy, usuario=self.prof.usuario)
        self.assertEqual(Recordatorio.objects.get(registro_vacuna=self.vencida).estado, EstadoRecordatorio.COMPLETADO)
        # y el comando no vuelve a avisar por la dosis ya superada
        antes = Recordatorio.objects.count()
        servicios.generar_recordatorios(dias=30)
        self.assertEqual(Recordatorio.objects.count(), antes)

    def test_solo_cuenta_la_ultima_aplicacion_de_cada_vacuna(self):
        self.aplicar(self.mascota, self.rabia, 5)  # refrescó la rabia hace 5 días: la vencida ya no importa
        servicios.generar_recordatorios(dias=30)
        self.assertFalse(Recordatorio.objects.filter(registro_vacuna=self.vencida).exists())

    def test_mascota_inactiva_no_genera_avisos(self):
        self.mascota.activa = False
        self.mascota.save()
        servicios.generar_recordatorios(dias=30)
        self.assertFalse(Recordatorio.objects.filter(mascota=self.mascota).exists())

    def test_controles_periodicos(self):
        c1 = ControlPeriodico.objects.create(mascota=self.mascota, motivo="Control anual", fecha_programada=self.hoy + timedelta(days=10))
        c2 = ControlPeriodico.objects.create(mascota=self.mascota, motivo="Lejano", fecha_programada=self.hoy + timedelta(days=90))
        c3 = ControlPeriodico.objects.create(mascota=self.mascota, motivo="Hecho", fecha_programada=self.hoy + timedelta(days=5), realizado=True)
        servicios.generar_recordatorios(dias=30)
        controles = Recordatorio.objects.filter(tipo=TipoRecordatorio.CONTROL)
        self.assertEqual(list(controles.values_list("control_id", flat=True)), [c1.pk])
        servicios.marcar_control_realizado(c1)
        self.assertEqual(controles.get().estado, EstadoRecordatorio.COMPLETADO)

    def test_control_vencido_se_marca_vencido(self):
        ControlPeriodico.objects.create(mascota=self.mascota, motivo="Atrasado", fecha_programada=self.hoy - timedelta(days=3))
        servicios.generar_recordatorios(dias=30)
        self.assertEqual(Recordatorio.objects.get(tipo="CONTROL").estado, EstadoRecordatorio.VENCIDO)

    def test_un_correo_que_falla_no_detiene_el_resto_y_se_reintenta(self):
        from unittest import mock

        with mock.patch("vacunacion.servicios.send_mail", side_effect=OSError("SMTP caído")),                 self.assertLogs("vacunacion.servicios", level="ERROR"):  # el error queda registrado (y no ensucia la salida)
            r = servicios.generar_recordatorios(dias=30)
        self.assertEqual((r["enviados"], r["errores_envio"]), (0, 3))
        self.assertEqual(servicios.generar_recordatorios(dias=30)["enviados"], 3)  # reintento

    def test_restriccion_unica_en_base_de_datos(self):
        servicios.generar_recordatorios(dias=30)
        rec = Recordatorio.objects.first()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Recordatorio.objects.create(
                mascota=rec.mascota, tipo=rec.tipo, fecha_objetivo=rec.fecha_objetivo, registro_vacuna=rec.registro_vacuna
            )

    def test_coherencia_tipo_origen_en_base_de_datos(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Recordatorio.objects.create(mascota=self.mascota, tipo="VACUNA", fecha_objetivo=self.hoy)


class PanelYPermisosTests(_VacunacionBase):
    def setUp(self):
        super().setUp()
        self.aplicar(self.mascota, self.rabia, 365 + 10)                                          # vencida
        self.aplicar(self.mascota, Vacuna.objects.create(nombre="V7", periodicidad_dias=100), 95)  # en 5 días
        self.aplicar(self.ajena, Vacuna.objects.create(nombre="Giardia", periodicidad_dias=100), 80)  # en 20 días (ajena)
        servicios.generar_recordatorios(dias=30)

    def test_panel_agrupa_por_urgencia(self):
        grupos = servicios.panel_recordatorios(self.admin)
        self.assertEqual([r.registro_vacuna.vacuna.nombre for r in grupos["vencidos"]], ["Rabia"])
        self.assertEqual([r.registro_vacuna.vacuna.nombre for r in grupos["semana"]], ["V7"])
        self.assertEqual([r.registro_vacuna.vacuna.nombre for r in grupos["mes"]], ["Giardia"])

    def test_tutor_ve_solo_sus_recordatorios_en_el_panel(self):
        grupos = servicios.panel_recordatorios(self.tutor.usuario)
        self.assertEqual((len(grupos["vencidos"]), len(grupos["semana"]), len(grupos["mes"])), (1, 1, 0))
        self.entrar(self.tutor.usuario)
        r = self.client.get(reverse("recordatorio_panel"))
        self.assertContains(r, "Rabia")
        self.assertContains(r, "urgencia-vencido")
        self.assertNotContains(r, "Giardia")
        self.assertNotContains(r, "Rex")

    def test_el_panel_carga_para_todos_los_roles(self):
        for usuario in (self.admin, self.recep, self.prof.usuario, self.tutor.usuario):
            self.entrar(usuario)
            self.assertEqual(self.client.get(reverse("recordatorio_panel")).status_code, 200, usuario.rol)

    def test_completados_no_aparecen_en_el_panel(self):
        Recordatorio.objects.update(estado=EstadoRecordatorio.COMPLETADO)
        grupos = servicios.panel_recordatorios(self.admin)
        self.assertEqual(sum(len(g) for g in grupos.values()), 0)

    # ---- web ----
    def test_veterinario_registra_vacuna_por_la_web(self):
        self.entrar(self.prof.usuario)
        r = self.client.post(reverse("registro_vacuna_crear"), {
            "mascota": self.ajena.pk, "vacuna": self.rabia.pk, "fecha_aplicacion": str(self.hoy), "lote": "A1",
        })
        self.assertRedirects(r, reverse("registro_vacuna_lista"))
        registro = RegistroVacuna.objects.get(mascota=self.ajena, vacuna=self.rabia)
        self.assertEqual(registro.proxima_dosis, self.hoy + timedelta(days=365))

    def test_web_rechaza_especie_incompatible_con_mensaje(self):
        self.entrar(self.prof.usuario)
        r = self.client.post(reverse("registro_vacuna_crear"), {
            "mascota": self.mascota.pk, "vacuna": self.triple.pk, "fecha_aplicacion": str(self.hoy),
        })
        self.assertContains(r, "es para gatos")

    def test_recepcion_y_tutor_no_registran_vacunas_en_la_web(self):
        for usuario in (self.recep, self.tutor.usuario):
            self.entrar(usuario)
            self.assertEqual(self.client.get(reverse("registro_vacuna_crear")).status_code, 403)

    def test_tutor_ve_solo_sus_vacunas_aplicadas_y_controles(self):
        ControlPeriodico.objects.create(mascota=self.ajena, motivo="Control ajeno", fecha_programada=self.hoy)
        self.entrar(self.tutor.usuario)
        self.assertNotContains(self.client.get(reverse("registro_vacuna_lista")), "Rex")
        self.assertNotContains(self.client.get(reverse("control_lista")), "Control ajeno")

    def test_recepcion_programa_control_y_tutor_no(self):
        self.entrar(self.recep)
        r = self.client.post(reverse("control_crear"), {
            "mascota": self.mascota.pk, "motivo": "Control de peso", "fecha_programada": str(self.hoy + timedelta(days=15)),
        })
        self.assertRedirects(r, reverse("control_lista"))
        control = ControlPeriodico.objects.get(motivo="Control de peso")
        self.entrar(self.tutor.usuario)
        self.assertEqual(self.client.get(reverse("control_crear")).status_code, 403)
        self.assertEqual(self.client.post(reverse("control_realizado", args=[control.pk])).status_code, 403)

    def test_catalogo_solo_lo_edita_veterinaria(self):
        self.entrar(self.recep)
        self.assertEqual(self.client.get(reverse("vacuna_lista")).status_code, 200)
        self.assertEqual(self.client.get(reverse("vacuna_crear")).status_code, 403)
        self.entrar(self.prof.usuario)
        r = self.client.post(reverse("vacuna_crear"), {"nombre": "Leptospirosis", "periodicidad_dias": 365, "activa": "on"})
        self.assertRedirects(r, reverse("vacuna_lista"))

    def test_vacuna_usada_se_desactiva_no_se_borra(self):
        self.entrar(self.admin)
        self.client.post(reverse("vacuna_eliminar", args=[self.rabia.pk]))
        self.rabia.refresh_from_db()
        self.assertFalse(self.rabia.activa)
        libre = Vacuna.objects.create(nombre="Sin uso", periodicidad_dias=30)
        self.client.post(reverse("vacuna_eliminar", args=[libre.pk]))
        self.assertFalse(Vacuna.objects.filter(pk=libre.pk).exists())

    # ---- API ----
    def cab(self, usuario):
        r = self.client.post("/api/auth/token/", {"username": usuario.username, "password": CLAVE}, content_type="application/json")
        return {"HTTP_AUTHORIZATION": f"Bearer {r.json()['access']}"}

    def test_api_tutor_ve_solo_sus_recordatorios(self):
        cab = self.cab(self.tutor.usuario)
        datos = self.client.get("/api/recordatorios/", **cab).json()
        self.assertEqual(datos["count"], 2)
        self.assertTrue(all(r["mascota_nombre"] == "Firulais" for r in datos["results"]))
        ajeno = Recordatorio.objects.filter(mascota=self.ajena).first()
        self.assertEqual(self.client.get(f"/api/recordatorios/{ajeno.pk}/", **cab).status_code, 404)

    def test_api_panel(self):
        datos = self.client.get("/api/recordatorios/panel/", **self.cab(self.tutor.usuario)).json()
        self.assertEqual((len(datos["vencidos"]), len(datos["semana"]), len(datos["mes"])), (1, 1, 0))
        self.assertLess(datos["vencidos"][0]["dias_restantes"], 0)

    def test_api_solo_admin_ejecuta_la_generacion(self):
        for usuario in (self.recep, self.prof.usuario, self.tutor.usuario):
            self.assertEqual(self.client.post("/api/recordatorios/generar/", **self.cab(usuario)).status_code, 403)
        r = self.client.post("/api/recordatorios/generar/", **self.cab(self.admin))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["creados"], 0)  # ya estaban generados: idempotente

    def test_api_registro_de_vacuna_calcula_proxima_dosis(self):
        r = self.client.post("/api/registros-vacuna/", {
            "mascota": self.ajena.pk, "vacuna": self.rabia.pk, "fecha_aplicacion": str(self.hoy), "lote": "Z9",
        }, content_type="application/json", **self.cab(self.prof.usuario))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["proxima_dosis"], str(self.hoy + timedelta(days=365)))

    def test_api_tutor_no_registra_vacunas_ni_ve_las_ajenas(self):
        cab = self.cab(self.tutor.usuario)
        r = self.client.post("/api/registros-vacuna/", {"mascota": self.mascota.pk, "vacuna": self.rabia.pk, "fecha_aplicacion": str(self.hoy)},
                             content_type="application/json", **cab)
        self.assertEqual(r.status_code, 403)
        nombres = {x["mascota_nombre"] for x in self.client.get("/api/registros-vacuna/", **cab).json()["results"]}
        self.assertEqual(nombres, {"Firulais"})

    def test_api_control_realizado(self):
        control = ControlPeriodico.objects.create(mascota=self.mascota, motivo="Revisión", fecha_programada=self.hoy + timedelta(days=3))
        self.assertEqual(self.client.post(f"/api/controles/{control.pk}/realizado/", **self.cab(self.tutor.usuario)).status_code, 403)
        self.assertEqual(self.client.post(f"/api/controles/{control.pk}/realizado/", **self.cab(self.recep)).status_code, 200)
        control.refresh_from_db()
        self.assertTrue(control.realizado)
