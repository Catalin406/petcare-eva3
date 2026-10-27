# ============================================================
# CLINICA/TESTS.PY / FICHA, ATENCIONES, EXÁMENES PRIVADOS Y PERMISOS
# ============================================================
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from agenda import servicios as servicios_agenda
from agenda.models import Cita, EstadoCita
from core.fabricas import CLAVE, crear_mascota, crear_profesional, crear_tutor, crear_usuario, fecha_futura, momento
from usuarios.models import Rol
from vacunacion.models import RegistroVacuna, Vacuna

from . import servicios
from .models import Atencion, Examen, FichaClinica, Receta

DATOS = {"anamnesis": "Tos hace 3 días", "diagnostico": "Traqueobronquitis", "tratamiento": "Reposo"}


class _ClinicaBase(TestCase):
    def setUp(self):
        self.carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.carpeta, ignore_errors=True)
        cfg = override_settings(ARCHIVOS_PRIVADOS_ROOT=Path(self.carpeta))
        cfg.enable()
        self.addCleanup(cfg.disable)

        self.prof = crear_profesional("vet1")
        self.prof2 = crear_profesional("vet2")
        self.recep = crear_usuario("recep", Rol.RECEPCIONISTA)
        self.admin = crear_usuario("admin", Rol.ADMINISTRADOR)
        self.tutor = crear_tutor("ana", "12345678")
        self.otro_tutor = crear_tutor("beto", "22222222")
        self.mascota = crear_mascota(self.tutor, "Firulais")
        self.ajena = crear_mascota(self.otro_tutor, "Rex")
        self.ficha = self.mascota.ficha
        self.dia = fecha_futura(5)

    def cita(self, estado=EstadoCita.PROGRAMADA, mascota=None, prof=None, hora="10:00"):
        cita = servicios_agenda.crear_cita(
            mascota=mascota or self.mascota, profesional=prof or self.prof, inicio=momento(self.dia, hora),
            motivo="Tos", creada_por=self.recep,
        )
        if estado == EstadoCita.CONFIRMADA:
            cita = servicios_agenda.cambiar_estado(cita, EstadoCita.CONFIRMADA, usuario=self.recep)
        return cita

    def entrar(self, usuario):
        self.client.logout()
        self.client.force_login(usuario)

    def pdf(self, nombre="rx.pdf", tamano=100):
        return SimpleUploadedFile(nombre, b"%PDF-1.4 " + b"x" * tamano, content_type="application/pdf")


class RegistrarAtencionTests(_ClinicaBase):
    def test_atencion_marca_la_cita_como_atendida(self):
        for estado in (EstadoCita.PROGRAMADA, EstadoCita.CONFIRMADA):
            with self.subTest(estado=estado):
                cita = self.cita(estado, hora="10:00" if estado == EstadoCita.PROGRAMADA else "11:00")
                atencion = servicios.registrar_atencion(veterinario=self.prof, ficha=self.ficha, cita=cita, datos=DATOS)
                cita.refresh_from_db()
                self.assertEqual(cita.estado, EstadoCita.ATENDIDA)
                self.assertEqual(atencion.cita, cita)
                self.assertEqual(cita.historial.last().estado_nuevo, EstadoCita.ATENDIDA)

    def test_es_atomico_si_algo_falla_no_se_guarda_nada(self):
        cita = self.cita()
        with self.assertRaises(ValidationError):
            servicios.registrar_atencion(
                veterinario=self.prof, ficha=self.ficha, cita=cita, datos=DATOS,
                recetas=[{"medicamento": "", "dosis": "1", "frecuencia": "c/8h", "duracion": "5 días"}],
            )
        cita.refresh_from_db()
        self.assertEqual(cita.estado, EstadoCita.PROGRAMADA)
        self.assertFalse(Atencion.objects.exists())

    def test_urgencia_sin_cita(self):
        atencion = servicios.registrar_atencion(veterinario=self.prof, ficha=self.ficha, datos=DATOS)
        self.assertIsNone(atencion.cita)
        self.assertEqual(Atencion.objects.count(), 1)

    def test_otro_veterinario_no_puede_atender_la_cita(self):
        cita = self.cita()
        with self.assertRaises(PermissionDenied):
            servicios.registrar_atencion(veterinario=self.prof2, ficha=self.ficha, cita=cita, datos=DATOS)

    def test_no_se_atiende_cita_cancelada_ni_dos_veces(self):
        cita = self.cita()
        servicios.registrar_atencion(veterinario=self.prof, ficha=self.ficha, cita=cita, datos=DATOS)
        with self.assertRaisesMessage(ValidationError, "atendida"):
            servicios.registrar_atencion(veterinario=self.prof, ficha=self.ficha, cita=cita, datos=DATOS)
        cancelada = self.cita(hora="12:00")
        servicios_agenda.cambiar_estado(cancelada, EstadoCita.CANCELADA, usuario=self.recep)
        with self.assertRaisesMessage(ValidationError, "cancelada"):
            servicios.registrar_atencion(veterinario=self.prof, ficha=self.ficha, cita=cancelada, datos=DATOS)

    def test_la_cita_debe_ser_de_la_misma_mascota(self):
        cita_ajena = self.cita(mascota=self.ajena)
        with self.assertRaisesMessage(ValidationError, "no corresponde"):
            servicios.registrar_atencion(veterinario=self.prof, ficha=self.ficha, cita=cita_ajena, datos=DATOS)

    def test_solo_un_veterinario_registra(self):
        with self.assertRaises(PermissionDenied):
            servicios.registrar_atencion(veterinario=self.recep, ficha=self.ficha, datos=DATOS)

    def test_mascota_inactiva_no_se_atiende(self):
        self.mascota.activa = False
        self.mascota.save()
        with self.assertRaisesMessage(ValidationError, "inactiva"):
            servicios.registrar_atencion(veterinario=self.prof, ficha=self.ficha, datos=DATOS)

    def test_guarda_recetas_y_examenes_y_actualiza_el_peso(self):
        atencion = servicios.registrar_atencion(
            veterinario=self.prof, ficha=self.ficha, datos={**DATOS, "peso_kg": "12.50", "temperatura_c": "38.5"},
            recetas=[{"medicamento": "Amoxicilina", "dosis": "250 mg", "frecuencia": "c/12h", "duracion": "7 días"}],
            examenes=[{"tipo": "Radiografía", "fecha": timezone.localdate(), "archivo": self.pdf()}],
        )
        self.assertEqual(atencion.recetas.count(), 1)
        self.assertEqual(atencion.examenes.count(), 1)
        self.mascota.refresh_from_db()
        self.assertEqual(str(self.mascota.peso), "12.50")

    def test_temperatura_imposible_rechazada(self):
        with self.assertRaises(ValidationError):
            servicios.registrar_atencion(veterinario=self.prof, ficha=self.ficha, datos={**DATOS, "temperatura_c": "60"})

    def test_solo_el_autor_corrige_su_atencion(self):
        atencion = servicios.registrar_atencion(veterinario=self.prof, ficha=self.ficha, datos=DATOS)
        with self.assertRaises(PermissionDenied):
            servicios.actualizar_atencion(atencion, usuario=self.prof2.usuario, datos={"diagnostico": "otro"})
        with self.assertRaises(PermissionDenied):
            servicios.actualizar_atencion(atencion, usuario=self.admin, datos={"diagnostico": "otro"})
        servicios.actualizar_atencion(atencion, usuario=self.prof.usuario, datos={"diagnostico": "Corregido"})
        atencion.refresh_from_db()
        self.assertEqual(atencion.diagnostico, "Corregido")

    def test_atencion_con_registros_no_se_puede_borrar(self):
        atencion = servicios.registrar_atencion(
            veterinario=self.prof, ficha=self.ficha, datos=DATOS,
            recetas=[{"medicamento": "X", "dosis": "1", "frecuencia": "1", "duracion": "1"}],
        )
        from django.db.models import ProtectedError

        with self.assertRaises(ProtectedError):
            atencion.delete()
        with self.assertRaises(ProtectedError):
            self.ficha.atenciones.model.objects.filter(pk=atencion.pk).delete()

    def test_constraint_de_temperatura_en_base_de_datos(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Atencion.objects.create(ficha=self.ficha, veterinario=self.prof, anamnesis="a", diagnostico="d", temperatura_c=99)


class LineaDeTiempoTests(_ClinicaBase):
    def test_incluye_atenciones_y_vacunas_en_orden(self):
        servicios.registrar_atencion(veterinario=self.prof, ficha=self.ficha, datos=DATOS)
        vacuna = Vacuna.objects.create(nombre="Rabia", periodicidad_dias=365)
        RegistroVacuna.objects.create(mascota=self.mascota, vacuna=vacuna, fecha_aplicacion=timezone.localdate() - timedelta(days=30))
        eventos = servicios.linea_de_tiempo(self.mascota)
        self.assertEqual([e["tipo"] for e in eventos], ["atencion", "vacuna"])


class PermisosWebClinicosTests(_ClinicaBase):
    def setUp(self):
        super().setUp()
        self.atencion = servicios.registrar_atencion(veterinario=self.prof, ficha=self.ficha, datos=DATOS)
        self.atencion_ajena = servicios.registrar_atencion(veterinario=self.prof, ficha=self.ajena.ficha, datos=DATOS)

    def test_recepcion_no_ve_fichas_ni_atenciones(self):
        self.entrar(self.recep)
        for url in (reverse("ficha_detalle", args=[self.mascota.pk]), reverse("atencion_detalle", args=[self.atencion.pk]),
                    reverse("ficha_editar", args=[self.mascota.pk])):
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_recepcion_no_edita_la_ficha_por_post(self):
        self.entrar(self.recep)
        r = self.client.post(reverse("ficha_editar", args=[self.mascota.pk]), {"alergias": "hackeado"})
        self.assertEqual(r.status_code, 403)
        self.ficha.refresh_from_db()
        self.assertEqual(self.ficha.alergias, "")

    def test_tutor_ve_la_ficha_de_su_mascota_en_solo_lectura(self):
        self.entrar(self.tutor.usuario)
        r = self.client.get(reverse("ficha_detalle", args=[self.mascota.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "solo lectura")
        self.assertNotContains(r, "Atención de urgencia")
        self.assertEqual(self.client.get(reverse("atencion_detalle", args=[self.atencion.pk])).status_code, 200)

    def test_tutor_no_ve_ficha_ni_atencion_ajena(self):
        self.entrar(self.tutor.usuario)
        self.assertEqual(self.client.get(reverse("ficha_detalle", args=[self.ajena.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("atencion_detalle", args=[self.atencion_ajena.pk])).status_code, 404)

    def test_tutor_no_edita_ficha_ni_crea_atenciones(self):
        self.entrar(self.tutor.usuario)
        self.assertEqual(self.client.post(reverse("ficha_editar", args=[self.mascota.pk]), {"alergias": "x"}).status_code, 403)
        self.assertEqual(self.client.get(reverse("atencion_crear")).status_code, 403)
        self.assertEqual(self.client.get(reverse("atencion_editar", args=[self.atencion.pk])).status_code, 403)

    def test_administrador_lee_pero_no_escribe_atenciones(self):
        self.entrar(self.admin)
        self.assertEqual(self.client.get(reverse("atencion_detalle", args=[self.atencion.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("atencion_crear")).status_code, 403)

    def test_veterinario_edita_la_ficha(self):
        self.entrar(self.prof.usuario)
        r = self.client.post(reverse("ficha_editar", args=[self.mascota.pk]),
                             {"alergias": "Penicilina", "antecedentes": "", "observaciones": ""})
        self.assertRedirects(r, reverse("ficha_detalle", args=[self.mascota.pk]))
        self.ficha.refresh_from_db()
        self.assertEqual(self.ficha.alergias, "Penicilina")

    def test_otro_veterinario_no_corrige_una_atencion_ajena(self):
        self.entrar(self.prof2.usuario)
        self.assertEqual(self.client.get(reverse("atencion_editar", args=[self.atencion.pk])).status_code, 403)

    def test_no_existe_ruta_para_borrar_atenciones(self):
        self.entrar(self.admin)
        for metodo in (self.client.get, self.client.post):
            self.assertEqual(metodo(f"/clinica/atenciones/{self.atencion.pk}/eliminar/").status_code, 404)
        self.assertTrue(Atencion.objects.filter(pk=self.atencion.pk).exists())

    def test_veterinario_registra_atencion_de_una_cita_por_la_web(self):
        cita = self.cita(hora="15:00")
        self.entrar(self.prof.usuario)
        datos = {
            "cita": cita.pk, "fecha": timezone.localtime().strftime("%Y-%m-%dT%H:%M"), **DATOS,
            "peso_kg": "10.2", "temperatura_c": "38.6",
            "recetas-TOTAL_FORMS": "2", "recetas-INITIAL_FORMS": "0",
            "recetas-0-medicamento": "Jarabe", "recetas-0-dosis": "5 ml", "recetas-0-frecuencia": "c/8h", "recetas-0-duracion": "5 días",
            "recetas-1-medicamento": "", "recetas-1-dosis": "", "recetas-1-frecuencia": "", "recetas-1-duracion": "",
            "examenes-TOTAL_FORMS": "2", "examenes-INITIAL_FORMS": "0",
            "examenes-0-tipo": "Hemograma", "examenes-0-fecha": str(timezone.localdate()), "examenes-0-archivo": self.pdf("hemo.pdf"),
            "examenes-1-tipo": "", "examenes-1-fecha": str(timezone.localdate()),
        }
        r = self.client.post(reverse("atencion_crear") + f"?cita={cita.pk}", datos)
        atencion = Atencion.objects.get(cita=cita)
        self.assertRedirects(r, reverse("atencion_detalle", args=[atencion.pk]))
        cita.refresh_from_db()
        self.assertEqual(cita.estado, EstadoCita.ATENDIDA)
        self.assertEqual(atencion.recetas.count(), 1)
        self.assertEqual(atencion.examenes.count(), 1)
        self.assertTrue(atencion.examenes.get().archivo.name.startswith("examenes/"))

    def test_urgencia_por_la_web_exige_elegir_mascota(self):
        self.entrar(self.prof.usuario)
        datos = {"fecha": timezone.localtime().strftime("%Y-%m-%dT%H:%M"), **DATOS,
                 "recetas-TOTAL_FORMS": "0", "recetas-INITIAL_FORMS": "0",
                 "examenes-TOTAL_FORMS": "0", "examenes-INITIAL_FORMS": "0"}
        r = self.client.post(reverse("atencion_crear"), datos)
        self.assertEqual(r.status_code, 200)
        r = self.client.post(reverse("atencion_crear"), {**datos, "mascota": self.mascota.pk})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Atencion.objects.filter(cita__isnull=True, ficha=self.ficha).count(), 2)  # 1 de setUp + esta

    def test_fecha_futura_de_atencion_rechazada(self):
        self.entrar(self.prof.usuario)
        manana = (timezone.localtime() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        r = self.client.post(reverse("atencion_crear"), {
            "fecha": manana, **DATOS, "mascota": self.mascota.pk,
            "recetas-TOTAL_FORMS": "0", "recetas-INITIAL_FORMS": "0", "examenes-TOTAL_FORMS": "0", "examenes-INITIAL_FORMS": "0",
        })
        self.assertContains(r, "no puede ser futura")


class ExamenPrivadoTests(_ClinicaBase):
    def setUp(self):
        super().setUp()
        self.atencion = servicios.registrar_atencion(
            veterinario=self.prof, ficha=self.ficha, datos=DATOS,
            examenes=[{"tipo": "Rx tórax", "fecha": timezone.localdate(), "archivo": self.pdf()}],
        )
        self.examen = self.atencion.examenes.get()
        self.url = reverse("examen_archivo", args=[self.examen.pk])

    def test_el_adjunto_se_guarda_fuera_de_static(self):
        from django.conf import settings

        self.assertTrue(self.examen.archivo.path.startswith(self.carpeta))
        self.assertNotIn(str(settings.STATIC_ROOT), self.examen.archivo.path)
        with self.assertRaises(ValueError):
            self.examen.archivo.url

    def test_anonimo_redirigido(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])

    def test_tutor_dueno_descarga(self):
        self.entrar(self.tutor.usuario)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertIn("no-store", r["Cache-Control"])
        self.assertEqual(b"".join(r.streaming_content)[:8], b"%PDF-1.4")

    def test_tutor_ajeno_recibe_404(self):
        self.entrar(self.otro_tutor.usuario)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_recepcion_recibe_403(self):
        self.entrar(self.recep)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_veterinario_y_administrador_acceden(self):
        for usuario in (self.prof.usuario, self.prof2.usuario, self.admin):
            self.entrar(usuario)
            self.assertEqual(self.client.get(self.url).status_code, 200, usuario.rol)

    def test_descarga_como_adjunto(self):
        self.entrar(self.admin)
        r = self.client.get(self.url + "?descargar=1")
        self.assertIn("attachment", r["Content-Disposition"])

    def test_archivo_borrado_del_disco_da_404(self):
        Path(self.examen.archivo.path).unlink()
        self.entrar(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_extension_no_permitida(self):
        with self.assertRaisesMessage(ValidationError, "no permitido"):
            servicios.registrar_atencion(
                veterinario=self.prof, ficha=self.ficha, datos=DATOS,
                examenes=[{"tipo": "Malo", "fecha": timezone.localdate(), "archivo": SimpleUploadedFile("a.exe", b"MZ")}],
            )

    def test_tamano_maximo(self):
        with self.assertRaisesMessage(ValidationError, "pesa demasiado"):
            servicios.registrar_atencion(
                veterinario=self.prof, ficha=self.ficha, datos=DATOS,
                examenes=[{"tipo": "Grande", "fecha": timezone.localdate(), "archivo": self.pdf("g.pdf", 5 * 1024 * 1024 + 10)}],
            )

    def test_el_examen_sin_adjunto_da_404(self):
        sin = Examen.objects.create(atencion=self.atencion, tipo="Sin archivo")
        self.entrar(self.admin)
        self.assertEqual(self.client.get(reverse("examen_archivo", args=[sin.pk])).status_code, 404)


class ApiClinicaTests(_ClinicaBase):
    def setUp(self):
        super().setUp()
        self.atencion = servicios.registrar_atencion(
            veterinario=self.prof, ficha=self.ficha, datos=DATOS,
            examenes=[{"tipo": "Rx", "fecha": timezone.localdate(), "archivo": self.pdf()}],
        )
        self.atencion_ajena = servicios.registrar_atencion(veterinario=self.prof, ficha=self.ajena.ficha, datos=DATOS)

    def cab(self, usuario):
        r = self.client.post("/api/auth/token/", {"username": usuario.username, "password": CLAVE}, content_type="application/json")
        return {"HTTP_AUTHORIZATION": f"Bearer {r.json()['access']}"}

    def test_recepcion_sin_acceso_a_nada_clinico(self):
        cab = self.cab(self.recep)
        for ruta in ("fichas", "atenciones", "recetas", "examenes"):
            self.assertEqual(self.client.get(f"/api/{ruta}/", **cab).status_code, 403, ruta)

    def test_tutor_ve_solo_lo_suyo(self):
        cab = self.cab(self.tutor.usuario)
        self.assertEqual(self.client.get("/api/atenciones/", **cab).json()["count"], 1)
        self.assertEqual(self.client.get(f"/api/atenciones/{self.atencion_ajena.pk}/", **cab).status_code, 404)
        self.assertEqual(self.client.get(f"/api/fichas/{self.ajena.ficha.pk}/", **cab).status_code, 404)
        self.assertEqual(self.client.get(f"/api/fichas/{self.ficha.pk}/", **cab).status_code, 200)

    def test_tutor_no_escribe(self):
        cab = self.cab(self.tutor.usuario)
        self.assertEqual(self.client.post("/api/atenciones/", {"ficha": self.ficha.pk, **DATOS}, content_type="application/json", **cab).status_code, 403)
        self.assertEqual(self.client.patch(f"/api/fichas/{self.ficha.pk}/", {"alergias": "x"}, content_type="application/json", **cab).status_code, 403)

    def test_no_existe_delete_de_atenciones(self):
        for usuario in (self.prof.usuario, self.admin):
            r = self.client.delete(f"/api/atenciones/{self.atencion.pk}/", **self.cab(usuario))
            self.assertIn(r.status_code, (403, 405), usuario.rol)
        self.assertTrue(Atencion.objects.filter(pk=self.atencion.pk).exists())

    def test_veterinario_crea_atencion_de_una_cita_con_recetas(self):
        cita = self.cita(hora="16:00")
        cab = self.cab(self.prof.usuario)
        r = self.client.post("/api/atenciones/", {
            "cita": cita.pk, "fecha": timezone.now().isoformat(), **DATOS,
            "recetas": [{"medicamento": "Ibuprofeno", "dosis": "1", "frecuencia": "c/8h", "duracion": "3 días"}],
        }, content_type="application/json", **cab)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(len(r.json()["recetas"]), 1)
        cita.refresh_from_db()
        self.assertEqual(cita.estado, EstadoCita.ATENDIDA)

    def test_veterinario_ajeno_no_puede_atender_la_cita_via_api(self):
        cita = self.cita(hora="16:00")
        r = self.client.post("/api/atenciones/", {"cita": cita.pk, "fecha": timezone.now().isoformat(), **DATOS},
                             content_type="application/json", **self.cab(self.prof2.usuario))
        self.assertEqual(r.status_code, 400)  # la cita ni siquiera es una opción para ese veterinario
        self.assertFalse(Atencion.objects.filter(cita=cita).exists())

    def test_examen_se_expone_como_url_protegida_y_se_descarga_con_jwt(self):
        examen = self.atencion.examenes.get()
        cab = self.cab(self.tutor.usuario)
        datos = self.client.get(f"/api/examenes/{examen.pk}/", **cab).json()
        self.assertTrue(datos["archivo_url"].endswith(f"/api/examenes/{examen.pk}/archivo/"))
        self.assertNotIn("/media/", datos["archivo_url"])
        self.assertNotIn("archivo", datos)
        self.assertEqual(self.client.get(datos["archivo_url"], **cab).status_code, 200)
        self.assertEqual(self.client.get(datos["archivo_url"]).status_code, 401)
        # tutor ajeno: 404; recepción: 403
        self.assertEqual(self.client.get(datos["archivo_url"], **self.cab(self.otro_tutor.usuario)).status_code, 404)
        self.assertEqual(self.client.get(datos["archivo_url"], **self.cab(self.recep)).status_code, 403)

    def test_veterinario_sube_examen_multipart_y_valida_extension(self):
        cab = self.cab(self.prof.usuario)
        r = self.client.post("/api/examenes/", {"atencion": self.atencion.pk, "tipo": "Eco", "fecha": str(timezone.localdate()),
                                                 "archivo": self.pdf("eco.pdf")}, **cab)
        self.assertEqual(r.status_code, 201, r.content)
        r = self.client.post("/api/examenes/", {"atencion": self.atencion.pk, "tipo": "Eco", "fecha": str(timezone.localdate()),
                                                 "archivo": SimpleUploadedFile("eco.exe", b"MZ")}, **cab)
        self.assertEqual(r.status_code, 400)

    def test_veterinario_no_agrega_examenes_a_atencion_de_otro(self):
        r = self.client.post("/api/examenes/", {"atencion": self.atencion.pk, "tipo": "Eco", "fecha": str(timezone.localdate())},
                             **self.cab(self.prof2.usuario))
        self.assertEqual(r.status_code, 400)

    def test_veterinario_actualiza_la_ficha(self):
        r = self.client.patch(f"/api/fichas/{self.ficha.pk}/", {"alergias": "Polen"}, content_type="application/json",
                              **self.cab(self.prof.usuario))
        self.assertEqual(r.status_code, 200)
        self.ficha.refresh_from_db()
        self.assertEqual(self.ficha.alergias, "Polen")
