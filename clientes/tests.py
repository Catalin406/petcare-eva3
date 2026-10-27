# ============================================================
# CLIENTES/TESTS.PY / TUTORES, MASCOTAS, PERMISOS Y FOTOS PRIVADAS
# ============================================================
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clinica.models import FichaClinica
from core.fabricas import CLAVE, crear_mascota, crear_profesional, crear_tutor, crear_usuario, rut_valido
from usuarios.models import Rol

from . import servicios
from .models import Mascota, Tutor

# PNG válido de 1x1 píxel (Pillow valida que la imagen sea real).
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7V\xbd\xfa\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TutorServicioTests(TestCase):
    def test_crear_tutor_crea_usuario_con_rol_tutor(self):
        tutor = crear_tutor("ana", "12345678")
        self.assertEqual(tutor.usuario.rol, Rol.TUTOR)
        self.assertFalse(tutor.usuario.is_staff)
        self.assertEqual(tutor.rut, "12345678-5")
        self.assertEqual(tutor.email, "ana@correo.test")

    def test_rut_se_normaliza_al_guardar(self):
        tutor = servicios.crear_tutor(
            username="luis", password=CLAVE, first_name="Luis", last_name="Soto", email="l@correo.test",
            rut="12.345.678-5", telefono="912345678", direccion="Calle 1",
        )
        self.assertEqual(tutor.rut, "12345678-5")

    def test_rut_invalido_rechazado(self):
        with self.assertRaises(ValidationError):
            servicios.crear_tutor(
                username="x", password=CLAVE, first_name="X", last_name="Y", email="x@correo.test",
                rut="12.345.678-9", telefono="912345678", direccion="Calle 1",
            )
        self.assertFalse(Tutor.objects.exists())

    def test_rut_unico(self):
        crear_tutor("ana", "12345678")
        with self.assertRaises(ValidationError):
            crear_tutor("ana2", "12345678")

    def test_rut_unico_tambien_en_la_base_de_datos(self):
        t = crear_tutor("ana", "12345678")
        otro = crear_usuario("otro", Rol.TUTOR)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Tutor.objects.create(usuario=otro, rut=t.rut, telefono="912345678", direccion="x")

    def test_correo_obligatorio(self):
        with self.assertRaises(ValidationError):
            servicios.crear_tutor(
                username="sin", password=CLAVE, first_name="S", last_name="C", email="",
                rut=rut_valido("12345678"), telefono="912345678", direccion="x",
            )

    def test_clave_debil_rechazada(self):
        with self.assertRaises(ValidationError):
            servicios.crear_tutor(
                username="debil", password="123", first_name="D", last_name="E", email="d@correo.test",
                rut=rut_valido("12345678"), telefono="912345678", direccion="x",
            )

    def test_eliminar_tutor_sin_mascotas_lo_borra(self):
        tutor = crear_tutor()
        self.assertEqual(servicios.eliminar_o_desactivar_tutor(tutor), "eliminado")
        self.assertFalse(Tutor.objects.exists())

    def test_eliminar_tutor_con_mascotas_lo_desactiva(self):
        tutor = crear_tutor()
        crear_mascota(tutor)
        self.assertEqual(servicios.eliminar_o_desactivar_tutor(tutor), "desactivado")
        tutor.usuario.refresh_from_db()
        self.assertFalse(tutor.usuario.is_active)
        self.assertEqual(Mascota.objects.count(), 1)


class MascotaTests(TestCase):
    def setUp(self):
        self.tutor = crear_tutor()

    def test_ficha_clinica_se_crea_sola(self):
        mascota = crear_mascota(self.tutor)
        self.assertTrue(FichaClinica.objects.filter(mascota=mascota).exists())

    def test_edad_calculada(self):
        hoy = timezone.localdate()
        mascota = crear_mascota(self.tutor, fecha_nacimiento=hoy.replace(year=hoy.year - 3) - timedelta(days=40))
        self.assertTrue(mascota.edad_texto.startswith("3 años"))
        cachorro = crear_mascota(self.tutor, "Cachorro", fecha_nacimiento=hoy - timedelta(days=65))
        self.assertEqual(cachorro.edad_texto, "2 meses")

    def test_fecha_de_nacimiento_futura_rechazada(self):
        mascota = Mascota(tutor=self.tutor, nombre="Futuro", especie="GATO", sexo="MACHO",
                          fecha_nacimiento=timezone.localdate() + timedelta(days=1))
        with self.assertRaises(ValidationError) as ctx:
            mascota.full_clean()
        self.assertIn("fecha_nacimiento", ctx.exception.message_dict)

    def test_microchip_unico_y_opcional(self):
        crear_mascota(self.tutor, "A", microchip="123456789012345")
        crear_mascota(self.tutor, "B")  # sin chip
        crear_mascota(self.tutor, "C")  # otra sin chip: no choca
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear_mascota(self.tutor, "D", microchip="123456789012345")

    def test_microchip_debe_tener_15_digitos(self):
        mascota = Mascota(tutor=self.tutor, nombre="Chip", especie="PERRO", sexo="MACHO",
                          fecha_nacimiento=timezone.localdate() - timedelta(days=500), microchip="123")
        with self.assertRaises(ValidationError):
            mascota.full_clean()

    def test_nombre_repetido_del_mismo_tutor_rechazado(self):
        crear_mascota(self.tutor, "Luna")
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear_mascota(self.tutor, "luna")

    def test_sin_historial_se_elimina(self):
        mascota = crear_mascota(self.tutor)
        self.assertEqual(servicios.eliminar_o_desactivar_mascota(mascota), "eliminada")
        self.assertFalse(Mascota.objects.exists())
        self.assertFalse(FichaClinica.objects.exists())

    def test_con_historial_se_desactiva(self):
        from agenda.models import Cita

        mascota = crear_mascota(self.tutor)
        prof = crear_profesional("vetx")
        inicio = timezone.now() - timedelta(days=5)
        Cita.objects.create(mascota=mascota, profesional=prof, inicio=inicio, fin=inicio + timedelta(minutes=30),
                            motivo="Control", estado="ATENDIDA")
        self.assertEqual(servicios.eliminar_o_desactivar_mascota(mascota), "desactivada")
        mascota.refresh_from_db()
        self.assertFalse(mascota.activa)
        self.assertTrue(FichaClinica.objects.filter(mascota=mascota).exists())


class _PermisosBase(TestCase):
    def setUp(self):
        self.admin = crear_usuario("admin1", Rol.ADMINISTRADOR)
        self.recep = crear_usuario("recep1", Rol.RECEPCIONISTA)
        self.vet = crear_profesional("vet1").usuario
        self.tutor_a = crear_tutor("tutora", "11111111")
        self.tutor_b = crear_tutor("tutorb", "22222222")
        self.mascota_a = crear_mascota(self.tutor_a, "Anita")
        self.mascota_b = crear_mascota(self.tutor_b, "Bruno")

    def entrar(self, usuario):
        self.client.logout()
        self.client.force_login(usuario)


class PermisosWebTests(_PermisosBase):
    def test_tutor_ve_solo_sus_mascotas_en_el_listado(self):
        self.entrar(self.tutor_a.usuario)
        respuesta = self.client.get(reverse("mascota_lista"))
        self.assertContains(respuesta, "Anita")
        self.assertNotContains(respuesta, "Bruno")

    def test_tutor_no_ve_mascota_ajena_404(self):
        self.entrar(self.tutor_a.usuario)
        self.assertEqual(self.client.get(reverse("mascota_detalle", args=[self.mascota_b.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("mascota_detalle", args=[self.mascota_a.pk])).status_code, 200)

    def test_tutor_no_edita_ni_crea_mascotas(self):
        self.entrar(self.tutor_a.usuario)
        self.assertEqual(self.client.get(reverse("mascota_crear")).status_code, 403)
        self.assertEqual(self.client.get(reverse("mascota_editar", args=[self.mascota_a.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("mascota_eliminar", args=[self.mascota_a.pk])).status_code, 403)

    def test_tutor_no_accede_a_tutores(self):
        self.entrar(self.tutor_a.usuario)
        self.assertEqual(self.client.get(reverse("tutor_lista")).status_code, 403)
        self.assertEqual(self.client.get(reverse("tutor_detalle", args=[self.tutor_b.pk])).status_code, 403)

    def test_veterinario_no_gestiona_tutores_pero_ve_mascotas(self):
        self.entrar(self.vet)
        self.assertEqual(self.client.get(reverse("tutor_lista")).status_code, 403)
        self.assertEqual(self.client.get(reverse("mascota_detalle", args=[self.mascota_a.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("mascota_crear")).status_code, 403)

    def test_recepcion_crea_tutor_y_mascota(self):
        self.entrar(self.recep)
        datos = {
            "username": "nuevo", "password": CLAVE, "first_name": "Nuevo", "last_name": "Tutor",
            "email": "nuevo@correo.test", "rut": "33.333.333-3", "telefono": "912345678", "direccion": "Calle 5",
        }
        datos["rut"] = rut_valido("33333333")
        respuesta = self.client.post(reverse("tutor_crear"), datos)
        tutor = Tutor.objects.get(usuario__username="nuevo")
        self.assertRedirects(respuesta, reverse("tutor_detalle", args=[tutor.pk]))
        respuesta = self.client.post(reverse("mascota_crear"), {
            "tutor": tutor.pk, "nombre": "Nuevita", "especie": "GATO", "sexo": "HEMBRA",
            "fecha_nacimiento": "2023-01-15", "activa": "on",
        })
        mascota = Mascota.objects.get(nombre="Nuevita")
        self.assertRedirects(respuesta, reverse("mascota_detalle", args=[mascota.pk]))
        self.assertTrue(FichaClinica.objects.filter(mascota=mascota).exists())

    def test_formulario_de_tutor_muestra_error_de_rut_claro(self):
        self.entrar(self.recep)
        respuesta = self.client.post(reverse("tutor_crear"), {
            "username": "malrut", "password": CLAVE, "first_name": "M", "last_name": "R",
            "email": "m@correo.test", "rut": "12.345.678-9", "telefono": "912345678", "direccion": "x",
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "dígito verificador")
        self.assertFalse(Tutor.objects.filter(usuario__username="malrut").exists())

    def test_rut_duplicado_con_otro_formato_se_rechaza(self):
        self.entrar(self.recep)
        respuesta = self.client.post(reverse("tutor_crear"), {
            "username": "dup", "password": CLAVE, "first_name": "D", "last_name": "U",
            "email": "d@correo.test", "rut": "11.111.111-1", "telefono": "912345678", "direccion": "x",
        })
        self.assertContains(respuesta, "Ya existe un tutor con ese RUT")

    def test_recepcion_edita_mascota_y_la_desactiva_si_tiene_historial(self):
        from agenda.models import Cita

        self.entrar(self.recep)
        prof = self.vet.profesional
        inicio = timezone.now() - timedelta(days=3)
        Cita.objects.create(mascota=self.mascota_a, profesional=prof, inicio=inicio, fin=inicio + timedelta(minutes=30),
                            motivo="Control", estado="ATENDIDA")
        self.client.post(reverse("mascota_eliminar", args=[self.mascota_a.pk]))
        self.mascota_a.refresh_from_db()
        self.assertFalse(self.mascota_a.activa)  # desactivada, no borrada

    def test_busqueda_de_mascotas(self):
        self.entrar(self.recep)
        respuesta = self.client.get(reverse("mascota_lista"), {"q": "Bruno"})
        self.assertContains(respuesta, "Bruno")
        self.assertNotContains(respuesta, "Anita")


class PermisosApiTests(_PermisosBase):
    def _token(self, usuario):
        respuesta = self.client.post(
            "/api/auth/token/", {"username": usuario.username, "password": CLAVE}, content_type="application/json"
        )
        return {"HTTP_AUTHORIZATION": f"Bearer {respuesta.json()['access']}"}

    def test_tutor_lista_solo_sus_mascotas(self):
        cabecera = self._token(self.tutor_a.usuario)
        datos = self.client.get("/api/mascotas/", **cabecera).json()
        self.assertEqual([m["nombre"] for m in datos["results"]], ["Anita"])

    def test_tutor_no_ve_mascota_ajena_404(self):
        cabecera = self._token(self.tutor_a.usuario)
        self.assertEqual(self.client.get(f"/api/mascotas/{self.mascota_b.pk}/", **cabecera).status_code, 404)
        self.assertEqual(self.client.get(f"/api/mascotas/{self.mascota_a.pk}/", **cabecera).status_code, 200)

    def test_tutor_no_puede_escribir_403(self):
        cabecera = self._token(self.tutor_a.usuario)
        r = self.client.post("/api/mascotas/", {"nombre": "X"}, content_type="application/json", **cabecera)
        self.assertEqual(r.status_code, 403)
        r = self.client.delete(f"/api/mascotas/{self.mascota_a.pk}/", **cabecera)
        self.assertEqual(r.status_code, 403)

    def test_tutor_solo_ve_su_propio_registro_de_tutor(self):
        cabecera = self._token(self.tutor_a.usuario)
        datos = self.client.get("/api/tutores/", **cabecera).json()
        self.assertEqual(datos["count"], 1)
        self.assertEqual(self.client.get(f"/api/tutores/{self.tutor_b.pk}/", **cabecera).status_code, 404)

    def test_veterinario_no_accede_a_tutores_api(self):
        self.assertEqual(self.client.get("/api/tutores/", **self._token(self.vet)).status_code, 403)

    def test_recepcion_crea_tutor_y_mascota_por_api(self):
        cabecera = self._token(self.recep)
        r = self.client.post("/api/tutores/", {
            "username": "apitutor", "password": CLAVE, "first_name": "Api", "last_name": "Tutor",
            "email": "api@correo.test", "rut": rut_valido("44444444"),
            "telefono": "912345678", "direccion": "Calle 9",
        }, content_type="application/json", **cabecera)
        self.assertEqual(r.status_code, 201, r.content)
        tutor_id = r.json()["id"]
        self.assertNotIn("password", r.json())
        r = self.client.post("/api/mascotas/", {
            "tutor": tutor_id, "nombre": "ApiPet", "especie": "PERRO", "sexo": "MACHO", "fecha_nacimiento": "2022-05-05",
        }, content_type="application/json", **cabecera)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(FichaClinica.objects.filter(mascota_id=r.json()["id"]).exists())

    def test_api_rechaza_fecha_futura_y_rut_malo(self):
        cabecera = self._token(self.recep)
        r = self.client.post("/api/mascotas/", {
            "tutor": self.tutor_a.pk, "nombre": "Futura", "especie": "PERRO", "sexo": "MACHO",
            "fecha_nacimiento": str(timezone.localdate() + timedelta(days=3)),
        }, content_type="application/json", **cabecera)
        self.assertEqual(r.status_code, 400)
        self.assertIn("fecha_nacimiento", r.json())
        r = self.client.post("/api/tutores/", {
            "username": "x1", "password": CLAVE, "first_name": "A", "last_name": "B", "email": "a@b.cl",
            "rut": "12345678-0", "telefono": "912345678", "direccion": "c",
        }, content_type="application/json", **cabecera)
        self.assertEqual(r.status_code, 400)
        self.assertIn("rut", r.json())

    def test_delete_con_historial_desactiva_y_responde_200(self):
        from agenda.models import Cita

        prof = self.vet.profesional
        inicio = timezone.now() - timedelta(days=2)
        Cita.objects.create(mascota=self.mascota_a, profesional=prof, inicio=inicio, fin=inicio + timedelta(minutes=30),
                            motivo="x", estado="ATENDIDA")
        r = self.client.delete(f"/api/mascotas/{self.mascota_a.pk}/", **self._token(self.admin))
        self.assertEqual(r.status_code, 200)
        self.mascota_a.refresh_from_db()
        self.assertFalse(self.mascota_a.activa)


class FotoPrivadaTests(_PermisosBase):
    """La foto no se sirve desde /media/: solo por una vista con login y permisos."""

    def setUp(self):
        super().setUp()
        self.carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.carpeta, ignore_errors=True)
        self.configuracion = override_settings(ARCHIVOS_PRIVADOS_ROOT=Path(self.carpeta))
        self.configuracion.enable()
        self.addCleanup(self.configuracion.disable)
        self.mascota_a.foto.save("foto.png", SimpleUploadedFile("foto.png", PNG_1X1, content_type="image/png"))

    def test_no_existe_ruta_de_media(self):
        self.entrar(self.admin)
        self.assertEqual(self.client.get("/media/mascotas/foto.png").status_code, 404)
        with self.assertRaises(ValueError):  # el almacenamiento no tiene URL pública
            self.mascota_a.foto.url

    def test_el_archivo_no_vive_en_static(self):
        from django.conf import settings

        self.assertNotIn(str(settings.STATIC_ROOT), self.mascota_a.foto.path)
        self.assertTrue(self.mascota_a.foto.path.startswith(self.carpeta))

    def test_formulario_de_edicion_con_foto_no_falla(self):
        self.entrar(self.recep)
        self.assertEqual(self.client.get(reverse("mascota_editar", args=[self.mascota_a.pk])).status_code, 200)

    def test_anonimo_redirigido_al_login(self):
        r = self.client.get(reverse("mascota_foto", args=[self.mascota_a.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])

    def test_tutor_dueno_ve_su_foto(self):
        self.entrar(self.tutor_a.usuario)
        r = self.client.get(reverse("mascota_foto", args=[self.mascota_a.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/png")
        self.assertIn("no-store", r["Cache-Control"])

    def test_tutor_ajeno_recibe_404(self):
        self.entrar(self.tutor_b.usuario)
        self.assertEqual(self.client.get(reverse("mascota_foto", args=[self.mascota_a.pk])).status_code, 404)

    def test_recepcion_y_veterinario_pueden_ver_la_foto(self):
        for usuario in (self.recep, self.vet, self.admin):
            self.entrar(usuario)
            self.assertEqual(self.client.get(reverse("mascota_foto", args=[self.mascota_a.pk])).status_code, 200)

    def test_mascota_sin_foto_da_404(self):
        self.entrar(self.admin)
        self.assertEqual(self.client.get(reverse("mascota_foto", args=[self.mascota_b.pk])).status_code, 404)

    def test_api_expone_url_protegida_no_ruta_de_media(self):
        r = self.client.post("/api/auth/token/", {"username": "tutora", "password": CLAVE}, content_type="application/json")
        cabecera = {"HTTP_AUTHORIZATION": f"Bearer {r.json()['access']}"}
        datos = self.client.get(f"/api/mascotas/{self.mascota_a.pk}/", **cabecera).json()
        self.assertTrue(datos["foto_url"].endswith(f"/api/mascotas/{self.mascota_a.pk}/foto/"))
        self.assertNotIn("/media/", datos["foto_url"])
        self.assertNotIn("foto", datos)  # el campo de escritura no se devuelve
        # y la URL entrega el binario con JWT
        self.assertEqual(self.client.get(datos["foto_url"], **cabecera).status_code, 200)
        # sin credenciales, no
        self.assertEqual(self.client.get(datos["foto_url"]).status_code, 401)

    def test_api_tutor_ajeno_no_descarga_la_foto(self):
        r = self.client.post("/api/auth/token/", {"username": "tutorb", "password": CLAVE}, content_type="application/json")
        cabecera = {"HTTP_AUTHORIZATION": f"Bearer {r.json()['access']}"}
        self.assertEqual(self.client.get(f"/api/mascotas/{self.mascota_a.pk}/foto/", **cabecera).status_code, 404)

    def test_foto_con_extension_no_permitida_rechazada(self):
        self.mascota_b.foto = SimpleUploadedFile("malo.exe", b"MZ", content_type="application/octet-stream")
        with self.assertRaises(ValidationError):
            self.mascota_b.full_clean()
