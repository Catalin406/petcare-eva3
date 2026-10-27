# ============================================================
# USUARIOS/TESTS.PY / PRUEBAS DE ROLES, LOGIN Y LOGOUT
# ============================================================
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Rol, Usuario

CLAVE = "ClaveSegura#2026"


def crear_usuario(username, rol, **extra):
    return Usuario.objects.create_user(username=username, password=CLAVE, rol=rol, **extra)


class RolesTests(TestCase):
    def test_rol_por_defecto_es_tutor(self):
        self.assertEqual(Usuario.objects.create_user("x", password=CLAVE).rol, Rol.TUTOR)

    def test_is_staff_solo_para_administrador(self):
        for rol in Rol.values:
            usuario = crear_usuario(f"u_{rol}", rol)
            self.assertEqual(usuario.is_staff, rol == Rol.ADMINISTRADOR, rol)

    def test_is_staff_se_corrige_al_cambiar_de_rol(self):
        usuario = crear_usuario("cambia", Rol.ADMINISTRADOR)
        usuario.rol = Rol.RECEPCIONISTA
        usuario.save()
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_staff)

    def test_no_se_puede_forzar_is_staff_a_mano(self):
        usuario = crear_usuario("forzado", Rol.TUTOR)
        usuario.is_staff = True
        usuario.save(update_fields=["is_staff"])
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_staff)

    def test_createsuperuser_es_administrador(self):
        admin = Usuario.objects.create_superuser("root", "root@petcare.cl", CLAVE)
        self.assertEqual(admin.rol, Rol.ADMINISTRADOR)
        self.assertTrue(admin.is_staff)

    def test_correo_unico_sin_distinguir_mayusculas(self):
        crear_usuario("a", Rol.TUTOR, email="Ana@correo.cl")
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear_usuario("b", Rol.TUTOR, email="ana@CORREO.cl")

    def test_correos_vacios_pueden_repetirse(self):
        crear_usuario("a", Rol.VETERINARIO)
        crear_usuario("b", Rol.VETERINARIO)


class LoginTests(TestCase):
    def setUp(self):
        self.usuario = crear_usuario("vet1", Rol.VETERINARIO)

    def test_inicio_exige_login(self):
        respuesta = self.client.get(reverse("inicio"))
        self.assertRedirects(respuesta, f"{reverse('login')}?next=/", fetch_redirect_response=False)

    def test_login_correcto_lleva_al_inicio(self):
        respuesta = self.client.post(reverse("login"), {"username": "vet1", "password": CLAVE})
        self.assertRedirects(respuesta, reverse("inicio"))

    def test_login_incorrecto_muestra_error(self):
        respuesta = self.client.post(reverse("login"), {"username": "vet1", "password": "mala"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "incorrectos")

    def test_logout_solo_por_post(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(SESSION_COOKIE_AGE=600)
    def test_la_sesion_usa_la_expiracion_configurada(self):
        self.client.post(reverse("login"), {"username": "vet1", "password": CLAVE})
        self.assertEqual(self.client.session.get_expiry_age(), 600)

    def test_ruta_inexistente_sin_login_redirige_al_login(self):
        # La red de seguridad global actúa antes de resolver la URL.
        respuesta = self.client.get("/cualquier-cosa/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login/", respuesta["Location"])


class TokenJWTTests(TestCase):
    def test_token_incluye_el_rol(self):
        import base64
        import json

        crear_usuario("tut", Rol.TUTOR)
        respuesta = self.client.post(
            "/api/auth/token/", {"username": "tut", "password": CLAVE}, content_type="application/json"
        )
        self.assertEqual(respuesta.status_code, 200)
        carga = respuesta.json()["access"].split(".")[1]
        carga += "=" * (-len(carga) % 4)
        self.assertEqual(json.loads(base64.urlsafe_b64decode(carga))["rol"], Rol.TUTOR)

    def test_token_con_clave_mala_da_401(self):
        crear_usuario("tut", Rol.TUTOR)
        respuesta = self.client.post(
            "/api/auth/token/", {"username": "tut", "password": "mala"}, content_type="application/json"
        )
        self.assertEqual(respuesta.status_code, 401)
