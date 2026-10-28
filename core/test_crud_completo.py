# ============================================================
# CORE/TEST_CRUD_COMPLETO.PY / CRUD WEB QUE FALTABA: VACUNAS APLICADAS, CONTROLES Y PROFESIONALES
# ============================================================
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from agenda.models import Cita, DisponibilidadSemanal, Profesional
from usuarios.models import Rol
from vacunacion import servicios as servicios_vacunacion
from vacunacion.models import ControlPeriodico, Recordatorio, RegistroVacuna, Vacuna

from .fabricas import CLAVE, crear_mascota, crear_profesional, crear_tutor, crear_usuario


class _Base(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.admin = crear_usuario("admin", Rol.ADMINISTRADOR)
        self.recep = crear_usuario("recep", Rol.RECEPCIONISTA)
        self.prof = crear_profesional("vet1")
        self.tutor = crear_tutor("ana", "12345678")
        self.otro = crear_tutor("beto", "22222222")
        self.mascota = crear_mascota(self.tutor, "Firulais")
        self.gato = crear_mascota(self.tutor, "Michi", "GATO")
        self.rabia = Vacuna.objects.create(nombre="Rabia", periodicidad_dias=365)
        self.triple = Vacuna.objects.create(nombre="Triple felina", especie_aplicable="GATO", periodicidad_dias=180)
        self.registro = RegistroVacuna.objects.create(
            mascota=self.mascota, vacuna=self.rabia, fecha_aplicacion=self.hoy - timedelta(days=360), veterinario=self.prof
        )

    def entrar(self, usuario):
        self.client.logout()
        self.client.force_login(usuario)


class EditarYEliminarVacunaAplicadaTests(_Base):
    def test_veterinario_corrige_fecha_y_lote_y_se_recalcula_la_proxima_dosis(self):
        self.entrar(self.prof.usuario)
        nueva = self.hoy - timedelta(days=30)
        r = self.client.post(reverse("registro_vacuna_editar", args=[self.registro.pk]), {
            "vacuna": self.rabia.pk, "fecha_aplicacion": nueva.isoformat(), "lote": "CORREGIDO",
        })
        self.assertRedirects(r, reverse("registro_vacuna_lista"))
        self.registro.refresh_from_db()
        self.assertEqual(self.registro.lote, "CORREGIDO")
        self.assertEqual(self.registro.proxima_dosis, nueva + timedelta(days=365))

    def test_la_mascota_no_se_puede_cambiar_al_corregir(self):
        self.entrar(self.prof.usuario)
        self.client.post(reverse("registro_vacuna_editar", args=[self.registro.pk]), {
            "mascota": self.gato.pk, "vacuna": self.rabia.pk, "fecha_aplicacion": self.hoy.isoformat(), "lote": "",
        })
        self.registro.refresh_from_db()
        self.assertEqual(self.registro.mascota, self.mascota)

    def test_rechaza_vacuna_de_otra_especie_con_mensaje(self):
        self.entrar(self.prof.usuario)
        r = self.client.post(reverse("registro_vacuna_editar", args=[self.registro.pk]), {
            "vacuna": self.triple.pk, "fecha_aplicacion": self.hoy.isoformat(), "lote": "",
        })
        self.assertContains(r, "es para gatos")
        self.registro.refresh_from_db()
        self.assertEqual(self.registro.vacuna, self.rabia)

    def test_rechaza_fecha_futura(self):
        self.entrar(self.prof.usuario)
        r = self.client.post(reverse("registro_vacuna_editar", args=[self.registro.pk]), {
            "vacuna": self.rabia.pk, "fecha_aplicacion": (self.hoy + timedelta(days=3)).isoformat(), "lote": "",
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "no puede ser futura")

    def test_los_recordatorios_obsoletos_se_descartan_al_corregir(self):
        servicios_vacunacion.generar_recordatorios(dias=30, enviar=False)
        antes = Recordatorio.objects.get(registro_vacuna=self.registro)
        self.entrar(self.prof.usuario)
        self.client.post(reverse("registro_vacuna_editar", args=[self.registro.pk]), {
            "vacuna": self.rabia.pk, "fecha_aplicacion": self.hoy.isoformat(), "lote": "",
        })
        self.assertFalse(Recordatorio.objects.filter(pk=antes.pk).exists())
        # y el comando no crea otro: la nueva dosis queda fuera de la ventana de 30 días
        servicios_vacunacion.generar_recordatorios(dias=30, enviar=False)
        self.assertFalse(Recordatorio.objects.filter(registro_vacuna=self.registro).exists())

    def test_recepcion_y_tutor_no_pueden_corregir(self):
        for usuario in (self.recep, self.tutor.usuario):
            self.entrar(usuario)
            url = reverse("registro_vacuna_editar", args=[self.registro.pk])
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {"vacuna": self.rabia.pk, "fecha_aplicacion": self.hoy.isoformat()}).status_code, 403)

    def test_solo_el_administrador_elimina_una_aplicacion(self):
        url = reverse("registro_vacuna_eliminar", args=[self.registro.pk])
        for usuario in (self.recep, self.prof.usuario, self.tutor.usuario):
            self.entrar(usuario)
            self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(RegistroVacuna.objects.filter(pk=self.registro.pk).exists())
        self.entrar(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)  # confirmación
        self.assertRedirects(self.client.post(url), reverse("registro_vacuna_lista"))
        self.assertFalse(RegistroVacuna.objects.filter(pk=self.registro.pk).exists())

    def test_los_botones_se_muestran_segun_el_rol(self):
        self.entrar(self.prof.usuario)
        r = self.client.get(reverse("registro_vacuna_lista"))
        self.assertContains(r, reverse("registro_vacuna_editar", args=[self.registro.pk]))
        self.assertNotContains(r, reverse("registro_vacuna_eliminar", args=[self.registro.pk]))
        self.entrar(self.admin)
        self.assertContains(self.client.get(reverse("registro_vacuna_lista")), reverse("registro_vacuna_eliminar", args=[self.registro.pk]))

    def test_api_actualiza_y_borra_con_los_mismos_permisos(self):
        def cab(u):
            r = self.client.post("/api/auth/token/", {"username": u.username, "password": CLAVE}, content_type="application/json")
            return {"HTTP_AUTHORIZATION": f"Bearer {r.json()['access']}"}

        url = f"/api/registros-vacuna/{self.registro.pk}/"
        r = self.client.patch(url, {"lote": "API-1"}, content_type="application/json", **cab(self.prof.usuario))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.client.delete(url, **cab(self.prof.usuario)).status_code, 403)
        self.assertEqual(self.client.delete(url, **cab(self.admin)).status_code, 204)


class EliminarControlTests(_Base):
    def setUp(self):
        super().setUp()
        self.control = ControlPeriodico.objects.create(mascota=self.mascota, motivo="Control", fecha_programada=self.hoy + timedelta(days=5))

    def test_recepcion_y_veterinario_eliminan_un_control_y_sus_recordatorios(self):
        servicios_vacunacion.generar_recordatorios(dias=30, enviar=False)
        self.assertTrue(Recordatorio.objects.filter(control=self.control).exists())
        self.entrar(self.recep)
        url = reverse("control_eliminar", args=[self.control.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertRedirects(self.client.post(url), reverse("control_lista"))
        self.assertFalse(ControlPeriodico.objects.filter(pk=self.control.pk).exists())
        self.assertFalse(Recordatorio.objects.filter(control_id=self.control.pk).exists())

    def test_el_tutor_no_elimina_ni_ve_los_controles_ajenos(self):
        self.entrar(self.tutor.usuario)
        self.assertEqual(self.client.post(reverse("control_eliminar", args=[self.control.pk])).status_code, 403)
        self.entrar(self.otro.usuario)
        self.assertEqual(self.client.post(reverse("control_eliminar", args=[self.control.pk])).status_code, 403)
        self.assertTrue(ControlPeriodico.objects.filter(pk=self.control.pk).exists())

    def test_un_control_inexistente_o_ajeno_da_404_para_quien_puede_gestionar(self):
        self.entrar(self.recep)
        self.assertEqual(self.client.post(reverse("control_eliminar", args=[99999])).status_code, 404)


class ProfesionalesWebTests(_Base):
    def test_solo_el_administrador_gestiona_profesionales(self):
        for nombre, args in (("profesional_lista", []), ("profesional_crear", []), ("profesional_editar", [self.prof.pk]),
                             ("profesional_eliminar", [self.prof.pk])):
            for usuario in (self.recep, self.prof.usuario, self.tutor.usuario):
                self.entrar(usuario)
                self.assertEqual(self.client.get(reverse(nombre, args=args)).status_code, 403, (nombre, usuario.rol))
            self.entrar(self.admin)
            self.assertEqual(self.client.get(reverse(nombre, args=args)).status_code, 200, nombre)

    def test_alta_con_un_veterinario_sin_ficha(self):
        nuevo = crear_usuario("vet_nuevo", Rol.VETERINARIO, first_name="Nuevo", last_name="Vet")
        self.entrar(self.admin)
        r = self.client.post(reverse("profesional_crear"), {"usuario": nuevo.pk, "especialidad": "Dermatología", "activo": "on"})
        self.assertRedirects(r, reverse("profesional_lista"))
        self.assertEqual(Profesional.objects.get(usuario=nuevo).especialidad, "Dermatología")

    def test_el_formulario_solo_ofrece_veterinarios_libres(self):
        crear_usuario("un_tutor", Rol.TUTOR)
        libre = crear_usuario("vet_libre", Rol.VETERINARIO)
        self.entrar(self.admin)
        r = self.client.get(reverse("profesional_crear"))
        opciones = [u.pk for u in r.context["form"].fields["usuario"].queryset]
        self.assertEqual(opciones, [libre.pk])  # no el tutor, no el veterinario que ya tiene ficha

    def test_no_se_puede_crear_dos_fichas_para_el_mismo_usuario(self):
        self.entrar(self.admin)
        r = self.client.post(reverse("profesional_crear"), {"usuario": self.prof.usuario.pk, "especialidad": "X", "activo": "on"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Profesional.objects.filter(usuario=self.prof.usuario).count(), 1)

    def test_edicion_cambia_especialidad_pero_no_el_usuario(self):
        otro = crear_usuario("vet_otro", Rol.VETERINARIO)
        self.entrar(self.admin)
        self.client.post(reverse("profesional_editar", args=[self.prof.pk]), {"usuario": otro.pk, "especialidad": "Cirugía", "activo": "on"})
        self.prof.refresh_from_db()
        self.assertEqual(self.prof.especialidad, "Cirugía")
        self.assertNotEqual(self.prof.usuario, otro)

    def test_con_historial_se_desactiva(self):
        inicio = timezone.now() - timedelta(days=2)
        Cita.objects.create(mascota=self.mascota, profesional=self.prof, inicio=inicio, fin=inicio + timedelta(minutes=30),
                            motivo="x", estado="ATENDIDA")
        self.entrar(self.admin)
        self.assertRedirects(self.client.post(reverse("profesional_eliminar", args=[self.prof.pk])), reverse("profesional_lista"))
        self.prof.refresh_from_db()
        self.assertFalse(self.prof.activo)

    def test_sin_historial_se_elimina_con_su_disponibilidad(self):
        libre = crear_profesional("vet_sin_historial")
        self.assertTrue(DisponibilidadSemanal.objects.filter(profesional=libre).exists())
        self.entrar(self.admin)
        self.client.post(reverse("profesional_eliminar", args=[libre.pk]))
        self.assertFalse(Profesional.objects.filter(pk=libre.pk).exists())
        self.assertFalse(DisponibilidadSemanal.objects.filter(profesional_id=libre.pk).exists())

    def test_un_profesional_desactivado_no_aparece_para_agendar(self):
        self.prof.activo = False
        self.prof.save()
        self.entrar(self.recep)
        r = self.client.get(reverse("cita_crear"))
        self.assertEqual(list(r.context["form"].fields["profesional"].queryset), [])

    def test_la_lista_y_la_navbar_del_administrador(self):
        self.entrar(self.admin)
        r = self.client.get(reverse("profesional_lista"))
        self.assertContains(r, self.prof.nombre)
        self.assertContains(r, reverse("profesional_lista"))  # enlace en la navbar
        self.entrar(self.recep)
        self.assertNotContains(self.client.get(reverse("inicio")), reverse("profesional_lista"))

    def test_api_delete_con_historial_desactiva_en_vez_de_dar_500(self):
        inicio = timezone.now() - timedelta(days=2)
        Cita.objects.create(mascota=self.mascota, profesional=self.prof, inicio=inicio, fin=inicio + timedelta(minutes=30),
                            motivo="x", estado="ATENDIDA")
        r = self.client.post("/api/auth/token/", {"username": "admin", "password": CLAVE}, content_type="application/json")
        cab = {"HTTP_AUTHORIZATION": f"Bearer {r.json()['access']}"}
        r = self.client.delete(f"/api/profesionales/{self.prof.pk}/", **cab)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["resultado"], "desactivado")
        libre = crear_profesional("vet_libre2")
        self.assertEqual(self.client.delete(f"/api/profesionales/{libre.pk}/", **cab).status_code, 204)
