# ============================================================
# CORE/TEST_SEGURIDAD.PY / SESIONES, CSRF, CONTRASEÑAS, COOKIES Y CONFIGURACIÓN
# ============================================================
import os
import re
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from usuarios.models import Rol

from .fabricas import CLAVE, crear_usuario

BASE = Path(settings.BASE_DIR)

# Variables de un servidor de producción simulado (no son secretos reales).
ENTORNO_PRODUCCION = {
    "DEBUG": "False",
    "SECRET_KEY": "k9$Xp2#vQ7!mZr4@Lw8&Tn5^Yb3*Hc6(Jd1)Fg0-Sa+Re=UiOoPlMqNzBxCvWy",
    "ALLOWED_HOSTS": "codelab-catalina.duckdns.org,54.152.231.63,localhost,127.0.0.1",
    "CSRF_TRUSTED_ORIGINS": "https://codelab-catalina.duckdns.org",
    "DETRAS_DE_PROXY_HTTPS": "True",
}


def ejecutar_manage(*argumentos, entorno=None):
    env = {**os.environ, **(entorno or {})}
    return subprocess.run(
        [sys.executable, "manage.py", *argumentos], cwd=BASE, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120
    )


def valor_de_settings(nombre, entorno):
    codigo = f"import django,os;os.environ['DJANGO_SETTINGS_MODULE']='config.settings';django.setup();from django.conf import settings;print(repr(settings.{nombre}))"
    r = subprocess.run([sys.executable, "-c", codigo], cwd=BASE, env={**os.environ, **entorno}, capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip()


class DespliegueSeguroTests(TestCase):
    def test_check_deploy_sin_advertencias_con_las_variables_de_produccion(self):
        r = ejecutar_manage("check", "--deploy", "--fail-level", "WARNING", entorno=ENTORNO_PRODUCCION)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("no issues", r.stderr + r.stdout)

    def test_con_proxy_las_cookies_son_seguras_y_se_redirige_a_https(self):
        for nombre in ("SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE", "SECURE_SSL_REDIRECT"):
            self.assertEqual(valor_de_settings(nombre, ENTORNO_PRODUCCION), "True", nombre)
        self.assertEqual(valor_de_settings("SECURE_PROXY_SSL_HEADER", ENTORNO_PRODUCCION), "('HTTP_X_FORWARDED_PROTO', 'https')")
        self.assertEqual(valor_de_settings("CSRF_TRUSTED_ORIGINS", ENTORNO_PRODUCCION), "['https://codelab-catalina.duckdns.org']")

    def test_en_local_sin_proxy_nada_de_eso_se_activa(self):
        local = {"DETRAS_DE_PROXY_HTTPS": "False", "DEBUG": "True"}
        self.assertEqual(valor_de_settings("SESSION_COOKIE_SECURE", local), "False")
        self.assertEqual(valor_de_settings("SECURE_SSL_REDIRECT", local), "False")

    def test_cookies_seguras_se_pueden_activar_por_separado(self):
        entorno = {"DETRAS_DE_PROXY_HTTPS": "False", "COOKIES_SEGURAS": "True"}
        self.assertEqual(valor_de_settings("SESSION_COOKIE_SECURE", entorno), "True")
        self.assertEqual(valor_de_settings("CSRF_COOKIE_SECURE", entorno), "True")

    def test_la_expiracion_de_sesion_se_configura_por_entorno(self):
        self.assertEqual(valor_de_settings("SESSION_COOKIE_AGE", {"SESSION_EXPIRA_SEGUNDOS": "900"}), "900")

    def test_secret_key_y_credenciales_de_bd_no_tienen_valor_por_defecto(self):
        # Sin default, si faltan en .env el proyecto no arranca (mejor eso que correr con una clave débil).
        settings_py = (BASE / "config" / "settings.py").read_text(encoding="utf-8")
        for variable in ("SECRET_KEY", "DB_NAME", "DB_USER", "DB_PASSWORD"):
            self.assertIn(f'config("{variable}")', settings_py, variable)

    def test_no_hay_secretos_escritos_en_el_codigo(self):
        settings_py = (BASE / "config" / "settings.py").read_text(encoding="utf-8")
        self.assertNotRegex(settings_py, r"SECRET_KEY\s*=\s*['\"]")
        self.assertNotRegex(settings_py, r"PASSWORD['\"]?\s*[:=]\s*['\"][^'\"]+['\"]")
        for variable in ("SECRET_KEY", "DEBUG", "ALLOWED_HOSTS", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST",
                         "CSRF_TRUSTED_ORIGINS", "DETRAS_DE_PROXY_HTTPS"):
            self.assertIn(f'config("{variable}"', settings_py, variable)

    def test_env_no_esta_en_el_repositorio_y_el_ejemplo_documenta_la_trampa_de_decouple(self):
        gitignore = (BASE / ".gitignore").read_text(encoding="utf-8")
        self.assertRegex(gitignore, r"(?m)^\.env$")
        self.assertIn("archivos_privados/", gitignore)
        ejemplo = (BASE / ".env.example").read_text(encoding="utf-8")
        self.assertRegex(ejemplo, r"(?i)vac[ií]a")
        for variable in ("SECRET_KEY", "DEBUG", "ALLOWED_HOSTS", "DB_NAME", "DB_USER", "DB_PASSWORD", "CSRF_TRUSTED_ORIGINS", "DETRAS_DE_PROXY_HTTPS"):
            self.assertIn(variable, ejemplo)

    def test_postgresql_es_el_unico_motor(self):
        self.assertEqual(settings.DATABASES["default"]["ENGINE"], "django.db.backends.postgresql")
        self.assertFalse(re.search(r"sqlite", (BASE / "config" / "settings.py").read_text(encoding="utf-8"), re.I))

    def test_requirements_con_versiones_fijas(self):
        lineas = [l for l in (BASE / "requirements.txt").read_text(encoding="utf-8").splitlines() if l and not l.startswith("#")]
        self.assertTrue(lineas)
        for linea in lineas:
            self.assertIn("==", linea, linea)
        nombres = " ".join(lineas).lower()
        for paquete in ("django==5.2", "djangorestframework==", "djangorestframework-simplejwt==", "drf-spectacular==",
                        "psycopg", "python-decouple==", "gunicorn=="):
            self.assertIn(paquete, nombres, paquete)

    def test_zona_horaria_e_idioma(self):
        self.assertEqual(settings.TIME_ZONE, "America/Santiago")
        self.assertEqual(settings.LANGUAGE_CODE, "es-cl")
        self.assertTrue(settings.USE_TZ)


class SesionesYCsrfTests(TestCase):
    def setUp(self):
        self.usuario = crear_usuario("recep", Rol.RECEPCIONISTA)

    def test_login_sin_token_csrf_es_rechazado(self):
        cliente = Client(enforce_csrf_checks=True)
        r = cliente.post(reverse("login"), {"username": "recep", "password": CLAVE})
        self.assertEqual(r.status_code, 403)

    def test_post_autenticado_sin_csrf_es_rechazado(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        self.assertEqual(cliente.post(reverse("logout")).status_code, 403)
        self.assertEqual(cliente.post(reverse("tutor_crear"), {}).status_code, 403)

    def test_login_con_token_csrf_funciona(self):
        cliente = Client(enforce_csrf_checks=True)
        pagina = cliente.get(reverse("login"))
        token = pagina.cookies["csrftoken"].value
        r = cliente.post(reverse("login"), {"username": "recep", "password": CLAVE, "csrfmiddlewaretoken": token})
        self.assertEqual(r.status_code, 302)

    def test_la_sesion_expira(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(reverse("inicio")).status_code, 200)
        Session.objects.update(expire_date=timezone.now() - timedelta(minutes=1))
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])

    def test_la_sesion_dura_lo_configurado_y_se_renueva(self):
        self.client.post(reverse("login"), {"username": "recep", "password": CLAVE})
        self.assertEqual(self.client.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)
        self.assertEqual(settings.SESSION_COOKIE_AGE, 1800)  # valor por defecto: 30 min
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)

    def test_cookie_de_sesion_httponly_y_samesite(self):
        r = self.client.post(reverse("login"), {"username": "recep", "password": CLAVE})
        cookie = r.cookies["sessionid"]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")

    def test_despues_de_cerrar_sesion_no_hay_acceso(self):
        self.client.force_login(self.usuario)
        self.client.post(reverse("logout"))
        self.assertEqual(self.client.get(reverse("tutor_lista")).status_code, 302)

    def test_next_externo_no_se_sigue_open_redirect(self):
        r = self.client.post(reverse("login") + "?next=//sitio-malicioso.com/", {"username": "recep", "password": CLAVE})
        self.assertRedirects(r, reverse("inicio"))

    def test_usuario_desactivado_no_entra(self):
        self.usuario.is_active = False
        self.usuario.save()
        r = self.client.post(reverse("login"), {"username": "recep", "password": CLAVE})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_cabeceras_de_seguridad(self):
        self.client.force_login(self.usuario)
        r = self.client.get(reverse("inicio"))
        self.assertEqual(r["X-Frame-Options"], "DENY")
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.assertIn("Referrer-Policy", r)


class ContrasenasTests(TestCase):
    def test_validadores_configurados(self):
        nombres = [v["NAME"].rsplit(".", 1)[-1] for v in settings.AUTH_PASSWORD_VALIDATORS]
        self.assertEqual(
            nombres,
            ["UserAttributeSimilarityValidator", "MinimumLengthValidator", "CommonPasswordValidator", "NumericPasswordValidator"],
        )

    def test_rechaza_claves_debiles(self):
        for clave in ("corta1", "1234567890123", "password123", "abcdefghij"):
            with self.subTest(clave=clave), self.assertRaises(ValidationError):
                validate_password(clave)

    def test_rechaza_clave_parecida_al_usuario(self):
        usuario = crear_usuario("catalina.quezada", Rol.TUTOR)
        with self.assertRaises(ValidationError):
            validate_password("catalina.quezada", usuario)

    def test_acepta_clave_robusta(self):
        validate_password("Una-Clave-Larga#2026")

    def test_las_claves_se_guardan_hasheadas(self):
        usuario = crear_usuario("hash", Rol.TUTOR)
        self.assertNotIn(CLAVE, usuario.password)
        self.assertTrue(usuario.password.startswith(("md5$", "pbkdf2_sha256$")))


class DocumentacionApiTests(TestCase):
    def test_swagger_y_esquema_sin_sesion_redirigen_al_login(self):
        for ruta in ("/api/docs/", "/api/schema/"):
            r = self.client.get(ruta)
            self.assertEqual(r.status_code, 302, ruta)
            self.assertTrue(r["Location"].startswith("/login/?next=" + ruta), r["Location"])

    def test_swagger_y_esquema_con_sesion_de_cualquier_rol(self):
        for rol in (Rol.ADMINISTRADOR, Rol.RECEPCIONISTA, Rol.VETERINARIO, Rol.TUTOR):
            self.client.logout()
            self.client.force_login(crear_usuario(f"doc_{rol}", rol))
            self.assertEqual(self.client.get("/api/docs/").status_code, 200, rol)
            r = self.client.get("/api/schema/")
            self.assertEqual(r.status_code, 200, rol)
            self.assertIn(b"/api/citas/", r.content)

    def test_los_endpoints_de_la_api_siguen_respondiendo_401_y_no_redirigen(self):
        self.assertEqual(self.client.get("/api/citas/").status_code, 401)

    def test_jwt_incluye_expiracion_y_refresh(self):
        crear_usuario("api", Rol.TUTOR)
        r = self.client.post("/api/auth/token/", {"username": "api", "password": CLAVE}, content_type="application/json")
        self.assertEqual(set(r.json()), {"access", "refresh"})
        refrescado = self.client.post("/api/auth/token/refresh/", {"refresh": r.json()["refresh"]}, content_type="application/json")
        self.assertEqual(refrescado.status_code, 200)
        self.assertEqual(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"], timedelta(minutes=30))

    def test_token_invalido_o_vencido_da_401(self):
        r = self.client.get("/api/mascotas/", HTTP_AUTHORIZATION="Bearer token.falso.xyz")
        self.assertEqual(r.status_code, 401)

    def test_la_api_permite_sesion_ademas_de_jwt(self):
        usuario = crear_usuario("ses", Rol.RECEPCIONISTA)
        self.client.force_login(usuario)
        self.assertEqual(self.client.get("/api/mascotas/").status_code, 200)

    def test_post_de_api_con_sesion_exige_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(crear_usuario("ses2", Rol.RECEPCIONISTA))
        r = cliente.post("/api/citas/", {}, content_type="application/json")
        self.assertEqual(r.status_code, 403)
