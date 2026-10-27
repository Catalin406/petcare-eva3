# ============================================================
# CORE/TESTS.PY / VALIDACIÓN DE RUT, ARCHIVOS Y LOGIN OBLIGATORIO GLOBAL
# ============================================================
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from usuarios.models import Rol

from .fabricas import crear_usuario
from .validadores import ValidadorArchivo, calcular_dv, normalizar_rut, validar_rut


class RutTests(SimpleTestCase):
    def test_digitos_verificadores_conocidos(self):
        # RUT reales de ejemplo ampliamente usados en documentación.
        self.assertEqual(calcular_dv("12345678"), "5")
        self.assertEqual(calcular_dv("11111111"), "1")
        self.assertEqual(calcular_dv("7654321"), "6")
        self.assertEqual(calcular_dv("20000000"), "5")

    def test_rut_valido_en_distintos_formatos(self):
        for texto in ("12.345.678-5", "12345678-5", "123456785", " 12.345.678-5 "):
            validar_rut(texto)  # no debe lanzar

    def test_normaliza_a_formato_estandar(self):
        self.assertEqual(normalizar_rut("12.345.678-5"), "12345678-5")
        self.assertEqual(normalizar_rut("24.965.051-k"), "24965051-K")

    def test_digito_verificador_incorrecto(self):
        with self.assertRaisesMessage(ValidationError, "dígito verificador"):
            validar_rut("12.345.678-9")

    def test_formato_invalido(self):
        for texto in ("", "abc", "1-9", "123", "12.345.678.9-5"):
            with self.assertRaises(ValidationError, msg=texto):
                validar_rut(texto)

    def test_dv_k_y_cero(self):
        # Resto 10 -> "K"; resto 11 -> "0" (calculados a mano: 24965051 suma 155, 14000000 suma 11).
        self.assertEqual(calcular_dv("24965051"), "K")
        self.assertEqual(calcular_dv("14000000"), "0")
        validar_rut("24.965.051-k")
        validar_rut("14.000.000-0")


class ValidadorArchivoTests(SimpleTestCase):
    def test_extension_no_permitida(self):
        validador = ValidadorArchivo(["pdf"])
        with self.assertRaisesMessage(ValidationError, "no permitido"):
            validador(SimpleUploadedFile("virus.exe", b"x"))

    def test_tamano_excedido(self):
        validador = ValidadorArchivo(["pdf"], max_mb=1)
        with self.assertRaisesMessage(ValidationError, "pesa demasiado"):
            validador(SimpleUploadedFile("grande.pdf", b"x" * (1024 * 1024 + 1)))

    def test_archivo_valido(self):
        ValidadorArchivo(["pdf"], max_mb=1)(SimpleUploadedFile("ok.pdf", b"%PDF-1.4"))


class LoginObligatorioGlobalTests(TestCase):
    """Ninguna vista web puede responder a un anónimo: todas redirigen al login."""

    def test_todas_las_rutas_web_exigen_login(self):
        rutas = [
            reverse("inicio"), reverse("tutor_lista"), reverse("tutor_crear"), reverse("tutor_detalle", args=[1]),
            reverse("mascota_lista"), reverse("mascota_crear"), reverse("mascota_detalle", args=[1]),
            reverse("mascota_foto", args=[1]), reverse("calendario"), reverse("cita_lista"), reverse("cita_crear"),
            reverse("cita_detalle", args=[1]), reverse("disponibilidad_lista"), reverse("ficha_detalle", args=[1]),
            reverse("atencion_crear"), reverse("atencion_detalle", args=[1]), reverse("examen_archivo", args=[1]),
            reverse("recordatorio_panel"), reverse("vacuna_lista"), reverse("registro_vacuna_lista"),
            reverse("control_lista"),
        ]
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)
                self.assertEqual(respuesta.status_code, 302, ruta)
                self.assertIn("/login/", respuesta["Location"], ruta)

    def test_post_anonimo_tambien_redirige(self):
        respuesta = self.client.post(reverse("cita_cambiar_estado", args=[1]), {"estado": "CANCELADA"})
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login/", respuesta["Location"])

    def test_api_responde_401_sin_credenciales(self):
        for ruta in ("/api/tutores/", "/api/mascotas/", "/api/citas/", "/api/atenciones/", "/api/recordatorios/"):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 401)

    def test_pagina_403_propia_para_rol_sin_permiso(self):
        crear_usuario("tut", Rol.TUTOR)
        self.client.login(username="tut", password="ClaveSegura#2026")
        respuesta = self.client.get(reverse("tutor_lista"))
        self.assertEqual(respuesta.status_code, 403)
        self.assertContains(respuesta, "No tienes permiso", status_code=403)

    def test_pagina_404_propia(self):
        crear_usuario("rec", Rol.RECEPCIONISTA)
        self.client.login(username="rec", password="ClaveSegura#2026")
        respuesta = self.client.get("/no-existe/")
        self.assertEqual(respuesta.status_code, 404)
        self.assertContains(respuesta, "No encontramos", status_code=404)
