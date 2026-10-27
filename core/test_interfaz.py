# ============================================================
# CORE/TEST_INTERFAZ.PY / NAVBAR POR ROL, INICIO, FOOTER Y PÁGINAS DE ERROR
# ============================================================
from datetime import timedelta
from unittest import mock

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from agenda import servicios as servicios_agenda
from agenda.models import Cita, EstadoCita
from usuarios.models import Rol
from vacunacion.models import RegistroVacuna, Vacuna
from vacunacion import servicios as servicios_vacunacion

from .fabricas import crear_mascota, crear_profesional, crear_tutor, crear_usuario, momento


class InterfazTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = crear_usuario("admin", Rol.ADMINISTRADOR)
        cls.recep = crear_usuario("recep", Rol.RECEPCIONISTA)
        cls.prof = crear_profesional("vet1")
        cls.tutor = crear_tutor("ana", "12345678")
        cls.otro = crear_tutor("beto", "22222222")
        cls.mascota = crear_mascota(cls.tutor, "Firulais")
        cls.ajena = crear_mascota(cls.otro, "Rex")
        # A las 12:00 de hoy (hora de Santiago): "hoy" no depende de a qué hora se corra la prueba.
        inicio = momento(timezone.localdate(), "12:00")
        cls.cita_hoy = Cita.objects.create(
            mascota=cls.mascota, profesional=cls.prof, inicio=inicio, fin=inicio + timedelta(minutes=30), motivo="Control hoy"
        )
        futura = timezone.now() + timedelta(days=2)
        cls.cita_futura = Cita.objects.create(
            mascota=cls.mascota, profesional=cls.prof, inicio=futura, fin=futura + timedelta(minutes=30), motivo="Control futuro"
        )
        vacuna = Vacuna.objects.create(nombre="Rabia", periodicidad_dias=365)
        RegistroVacuna.objects.create(mascota=cls.mascota, vacuna=vacuna, fecha_aplicacion=timezone.localdate() - timedelta(days=400))
        servicios_vacunacion.generar_recordatorios(dias=30, enviar=False)

    def entrar(self, usuario):
        self.client.logout()
        self.client.force_login(usuario)

    def test_navbar_de_cada_rol_muestra_solo_sus_accesos(self):
        esperado = {
            Rol.ADMINISTRADOR: ["Tutores", "Mascotas", "Citas", "Administración", "Disponibilidad"],
            Rol.RECEPCIONISTA: ["Tutores", "Mascotas", "Citas", "Calendario"],
            Rol.VETERINARIO: ["Mi agenda", "Pacientes", "Disponibilidad"],
            Rol.TUTOR: ["Mis mascotas", "Mis citas", "Pedir hora", "Recordatorios"],
        }
        prohibido = {
            Rol.ADMINISTRADOR: [],
            Rol.RECEPCIONISTA: ["Administración", "Disponibilidad"],
            Rol.VETERINARIO: ["Tutores", "Administración"],
            Rol.TUTOR: ["Tutores", "Administración", "Disponibilidad", "Catálogo de vacunas"],
        }
        usuarios = {Rol.ADMINISTRADOR: self.admin, Rol.RECEPCIONISTA: self.recep, Rol.VETERINARIO: self.prof.usuario, Rol.TUTOR: self.tutor.usuario}
        for rol, usuario in usuarios.items():
            self.entrar(usuario)
            html = self.client.get(reverse("inicio")).content.decode()
            for texto in esperado[rol]:
                self.assertIn(texto, html, f"{rol} debería ver «{texto}»")
            for texto in prohibido[rol]:
                self.assertNotIn(f"> {texto}<", html.replace("</i> ", "> ").replace("\n", ""), f"{rol} no debería ver «{texto}»")

    def test_logout_es_un_formulario_post_con_csrf(self):
        self.entrar(self.recep)
        html = self.client.get(reverse("inicio")).content.decode()
        self.assertIn('method="post" action="/logout/"', html)
        self.assertIn("csrfmiddlewaretoken", html)

    def test_footer_muestra_el_nombre_del_alumno_desde_settings(self):
        self.entrar(self.recep)
        self.assertContains(self.client.get(reverse("inicio")), "Catalina Quezada Sanzana")
        with override_settings(ALUMNO_NOMBRE="Otra Persona"):
            self.assertContains(self.client.get(reverse("inicio")), "Otra Persona")

    def test_inicio_del_veterinario_muestra_sus_citas_de_hoy(self):
        self.entrar(self.prof.usuario)
        r = self.client.get(reverse("inicio"))
        self.assertContains(r, "Tu agenda de hoy")
        self.assertContains(r, "Control hoy")

    def test_inicio_del_tutor_muestra_solo_lo_suyo(self):
        inicio = timezone.now() + timedelta(days=3)
        Cita.objects.create(mascota=self.ajena, profesional=self.prof, inicio=inicio, fin=inicio + timedelta(minutes=30), motivo="Cita ajena")
        self.entrar(self.tutor.usuario)
        r = self.client.get(reverse("inicio"))
        self.assertContains(r, "Control futuro")
        self.assertNotContains(r, "Cita ajena")
        self.assertNotContains(r, "Rex")

    def test_inicio_de_recepcion_cuenta_citas_y_recordatorios(self):
        self.entrar(self.recep)
        r = self.client.get(reverse("inicio"))
        self.assertContains(r, "Agenda de hoy")
        self.assertContains(r, "Recordatorios vencidos")

    def test_detalle_de_mascota_muestra_citas_vacunas_y_recordatorios_por_rol(self):
        self.entrar(self.tutor.usuario)
        r = self.client.get(reverse("mascota_detalle", args=[self.mascota.pk]))
        self.assertContains(r, "Control futuro")
        self.assertContains(r, "Rabia")
        self.assertContains(r, "urgencia-vencido")

    def test_pagina_500_propia(self):
        cliente = Client(raise_request_exception=False)
        cliente.force_login(self.recep)
        with mock.patch("core.views.InicioView.get", side_effect=RuntimeError("falla de prueba")):
            r = cliente.get(reverse("inicio"))
        self.assertEqual(r.status_code, 500)
        self.assertContains(r, "Algo salió mal", status_code=500)

    def test_paginas_de_error_usan_el_mismo_diseno(self):
        self.entrar(self.tutor.usuario)
        r = self.client.get(reverse("tutor_lista"))
        self.assertContains(r, "navbar-petcare", status_code=403)
        self.assertContains(r, "tema.css", status_code=403)
        r = self.client.get("/ruta/que/no/existe/")
        self.assertContains(r, "navbar-petcare", status_code=404)

    def test_el_tema_define_la_paleta_de_la_referencia(self):
        from django.contrib.staticfiles import finders

        css = open(finders.find("css/tema.css"), encoding="utf-8").read()
        for color in ("#f4a7b9", "#fbd3dd", "#c9627d", "#dcc6ad", "#f1e6d9", "#b08968", "#7f5c42", "#fff4f7", "#4a3b36", "#7a6660", "#f0d9df"):
            self.assertIn(color, css, color)
        self.assertIn("Nunito", css)

    def test_bootstrap_y_iconos_se_cargan_en_las_paginas(self):
        self.entrar(self.recep)
        html = self.client.get(reverse("inicio")).content.decode()
        self.assertIn("bootstrap@5.3", html)
        self.assertIn("bootstrap-icons", html)
