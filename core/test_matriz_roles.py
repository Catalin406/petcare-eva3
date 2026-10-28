# ============================================================
# CORE/TEST_MATRIZ_ROLES.PY / MATRIZ COMPLETA DE PERMISOS: ROL × RUTA (web y API)
# Una sola tabla que documenta (y comprueba) qué puede abrir cada rol.
# ============================================================
from django.test import TestCase
from django.urls import reverse

from usuarios.models import Rol

from .fabricas import CLAVE, crear_mascota, crear_profesional, crear_tutor, crear_usuario

A, R, V, T = Rol.ADMINISTRADOR, Rol.RECEPCIONISTA, Rol.VETERINARIO, Rol.TUTOR

# (nombre de la ruta, ¿lleva el id de la mascota propia del tutor?, {rol: código esperado})
MATRIZ_WEB = [
    ("tutor_lista",            False, {A: 200, R: 200, V: 403, T: 403}),
    ("tutor_crear",            False, {A: 200, R: 200, V: 403, T: 403}),
    ("mascota_lista",          False, {A: 200, R: 200, V: 200, T: 200}),
    ("mascota_crear",          False, {A: 200, R: 200, V: 403, T: 403}),
    ("mascota_detalle",        True,  {A: 200, R: 200, V: 200, T: 200}),
    ("mascota_editar",         True,  {A: 200, R: 200, V: 403, T: 403}),
    ("calendario",             False, {A: 200, R: 200, V: 200, T: 200}),
    ("cita_lista",             False, {A: 200, R: 200, V: 200, T: 200}),
    ("cita_crear",             False, {A: 200, R: 200, V: 403, T: 200}),
    ("disponibilidad_lista",   False, {A: 200, R: 403, V: 200, T: 403}),
    ("disponibilidad_crear",   False, {A: 200, R: 403, V: 200, T: 403}),
    ("bloqueo_crear",          False, {A: 200, R: 403, V: 200, T: 403}),
    ("ficha_detalle",          True,  {A: 200, R: 403, V: 200, T: 200}),
    ("ficha_editar",           True,  {A: 200, R: 403, V: 200, T: 403}),
    ("atencion_crear",         False, {A: 403, R: 403, V: 200, T: 403}),
    ("recordatorio_panel",     False, {A: 200, R: 200, V: 200, T: 200}),
    ("vacuna_lista",           False, {A: 200, R: 200, V: 200, T: 403}),
    ("vacuna_crear",           False, {A: 200, R: 403, V: 200, T: 403}),
    ("registro_vacuna_lista",  False, {A: 200, R: 200, V: 200, T: 200}),
    ("registro_vacuna_crear",  False, {A: 200, R: 403, V: 200, T: 403}),
    ("control_lista",          False, {A: 200, R: 200, V: 200, T: 200}),
    ("control_crear",          False, {A: 200, R: 200, V: 200, T: 403}),
    ("profesional_lista",      False, {A: 200, R: 403, V: 403, T: 403}),
    ("profesional_crear",      False, {A: 200, R: 403, V: 403, T: 403}),
]

# (ruta de la API, método, {rol: código esperado})
MATRIZ_API = [
    ("/api/tutores/",         "get", {A: 200, R: 200, V: 403, T: 200}),
    ("/api/mascotas/",        "get", {A: 200, R: 200, V: 200, T: 200}),
    ("/api/mascotas/",        "post", {A: 400, R: 400, V: 403, T: 403}),   # 400: llegó a validar el cuerpo vacío
    ("/api/profesionales/",   "get", {A: 200, R: 200, V: 200, T: 200}),
    ("/api/profesionales/",   "post", {A: 400, R: 403, V: 403, T: 403}),
    ("/api/disponibilidades/", "get", {A: 200, R: 200, V: 200, T: 403}),
    ("/api/bloqueos/",        "get", {A: 200, R: 200, V: 200, T: 403}),
    ("/api/citas/",           "get", {A: 200, R: 200, V: 200, T: 200}),
    ("/api/citas/",           "post", {A: 400, R: 400, V: 403, T: 400}),
    ("/api/fichas/",          "get", {A: 200, R: 403, V: 200, T: 200}),
    ("/api/atenciones/",      "get", {A: 200, R: 403, V: 200, T: 200}),
    ("/api/atenciones/",      "post", {A: 403, R: 403, V: 400, T: 403}),
    ("/api/recetas/",         "get", {A: 200, R: 403, V: 200, T: 200}),
    ("/api/examenes/",        "get", {A: 200, R: 403, V: 200, T: 200}),
    ("/api/vacunas/",         "get", {A: 200, R: 200, V: 200, T: 200}),
    ("/api/vacunas/",         "post", {A: 400, R: 403, V: 400, T: 403}),
    ("/api/registros-vacuna/", "get", {A: 200, R: 200, V: 200, T: 200}),
    ("/api/controles/",       "get", {A: 200, R: 200, V: 200, T: 200}),
    ("/api/recordatorios/",   "get", {A: 200, R: 200, V: 200, T: 200}),
    ("/api/recordatorios/generar/", "post", {A: 200, R: 403, V: 403, T: 403}),
]


class MatrizRolesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuarios = {
            A: crear_usuario("admin", A),
            R: crear_usuario("recep", R),
            V: crear_profesional("vet1").usuario,
        }
        cls.tutor = crear_tutor("ana", "12345678")
        cls.usuarios[T] = cls.tutor.usuario
        cls.mascota = crear_mascota(cls.tutor, "Firulais")

    def _token(self, usuario):
        r = self.client.post("/api/auth/token/", {"username": usuario.username, "password": CLAVE}, content_type="application/json")
        return {"HTTP_AUTHORIZATION": f"Bearer {r.json()['access']}"}

    def test_matriz_web(self):
        for nombre, con_mascota, esperado in MATRIZ_WEB:
            for rol, codigo in esperado.items():
                with self.subTest(ruta=nombre, rol=rol):
                    self.client.logout()
                    self.client.force_login(self.usuarios[rol])
                    url = reverse(nombre, args=[self.mascota.pk]) if con_mascota else reverse(nombre)
                    self.assertEqual(self.client.get(url).status_code, codigo)

    def test_matriz_api(self):
        for ruta, metodo, esperado in MATRIZ_API:
            for rol, codigo in esperado.items():
                with self.subTest(ruta=ruta, metodo=metodo, rol=rol):
                    cabecera = self._token(self.usuarios[rol])
                    llamada = getattr(self.client, metodo)
                    r = llamada(ruta, {}, content_type="application/json", **cabecera) if metodo == "post" else llamada(ruta, **cabecera)
                    self.assertEqual(r.status_code, codigo, r.content[:200])

    def test_admin_de_django_solo_para_el_rol_administrador(self):
        for rol, usuario in self.usuarios.items():
            self.client.logout()
            self.client.force_login(usuario)
            esperado = 200 if rol == A else 302
            self.assertEqual(self.client.get(reverse("admin:index")).status_code, esperado, rol)
