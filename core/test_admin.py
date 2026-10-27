# ============================================================
# CORE/TEST_ADMIN.PY / DJANGO ADMIN: TODOS LOS MODELOS, MARCA Y ACCIONES
# ============================================================
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path

from django.contrib import admin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from agenda import servicios as servicios_agenda
from agenda.models import BloqueoAgenda, Cita, EstadoCita
from clinica import servicios as servicios_clinica
from usuarios.models import Rol
from vacunacion import servicios as servicios_vacunacion
from vacunacion.models import ControlPeriodico, Recordatorio, RegistroVacuna, Vacuna

from .fabricas import crear_mascota, crear_profesional, crear_tutor, crear_usuario, fecha_futura, momento


class AdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.carpeta = tempfile.mkdtemp()
        cls.configuracion = override_settings(ARCHIVOS_PRIVADOS_ROOT=Path(cls.carpeta))
        cls.configuracion.enable()
        cls.addClassCleanup(shutil.rmtree, cls.carpeta, ignore_errors=True)
        cls.addClassCleanup(cls.configuracion.disable)

        cls.admin = crear_usuario("admin", Rol.ADMINISTRADOR)
        cls.recep = crear_usuario("recep", Rol.RECEPCIONISTA)
        cls.prof = crear_profesional("vet1")
        cls.tutor = crear_tutor("ana", "12345678")
        cls.mascota = crear_mascota(cls.tutor, "Firulais")
        cls.mascota.foto.save(
            "f.png", SimpleUploadedFile("f.png", b"\x89PNG\r\n\x1a\n", content_type="image/png"), save=True
        )
        cls.dia = fecha_futura(6)
        cls.cita = servicios_agenda.crear_cita(
            mascota=cls.mascota, profesional=cls.prof, inicio=momento(cls.dia, "10:00"), motivo="Control", creada_por=cls.recep
        )
        cls.atencion = servicios_clinica.registrar_atencion(
            veterinario=cls.prof, ficha=cls.mascota.ficha, datos={"anamnesis": "a", "diagnostico": "d"},
            examenes=[{"tipo": "Rx", "fecha": timezone.localdate(),
                       "archivo": SimpleUploadedFile("rx.pdf", b"%PDF-1.4 x", content_type="application/pdf")}],
            recetas=[{"medicamento": "M", "dosis": "1", "frecuencia": "1", "duracion": "1"}],
        )
        BloqueoAgenda.objects.create(profesional=cls.prof, inicio=momento(cls.dia, "00:00"),
                                     fin=momento(cls.dia + timedelta(days=1), "00:00"), motivo="Feriado")
        vacuna = Vacuna.objects.create(nombre="Rabia", periodicidad_dias=365)
        RegistroVacuna.objects.create(mascota=cls.mascota, vacuna=vacuna,
                                      fecha_aplicacion=timezone.localdate() - timedelta(days=360))
        ControlPeriodico.objects.create(mascota=cls.mascota, motivo="Control", fecha_programada=timezone.localdate() + timedelta(days=4))
        servicios_vacunacion.generar_recordatorios(dias=30, enviar=False)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_todos_los_modelos_del_dominio_estan_registrados(self):
        from django.apps import apps

        propios = [m for app in ("usuarios", "clientes", "agenda", "clinica", "vacunacion") for m in apps.get_app_config(app).get_models()]
        faltan = [m.__name__ for m in propios if m not in admin.site._registry]
        self.assertEqual(faltan, [])

    def test_cada_modelo_tiene_personalizacion_util(self):
        for modelo, ma in admin.site._registry.items():
            if modelo._meta.app_label not in ("usuarios", "clientes", "agenda", "clinica", "vacunacion"):
                continue
            with self.subTest(modelo=modelo.__name__):
                self.assertTrue(len(ma.list_display) >= 2, "list_display con columnas útiles")
                self.assertTrue(ma.list_filter or ma.search_fields, "filtros o búsqueda")
                self.assertTrue(ma.search_fields, "search_fields")

    def test_modelos_con_fechas_tienen_date_hierarchy(self):
        con_fecha = ("Cita", "Atencion", "RegistroVacuna", "Recordatorio", "ControlPeriodico", "BloqueoAgenda", "Examen", "Tutor", "Mascota")
        for modelo, ma in admin.site._registry.items():
            if modelo.__name__ in con_fecha:
                self.assertTrue(ma.date_hierarchy, modelo.__name__)

    def test_inlines_pedidos_por_la_rubrica(self):
        from clientes.admin import MascotaInline, TutorAdmin
        from clinica.admin import AtencionAdmin, ExamenInline, RecetaInline

        self.assertIn(MascotaInline, TutorAdmin.inlines)
        self.assertEqual({RecetaInline, ExamenInline}, set(AtencionAdmin.inlines))

    def test_listas_agregar_y_editar_cargan_sin_error(self):
        for modelo, ma in admin.site._registry.items():
            app, nombre = modelo._meta.app_label, modelo._meta.model_name
            if app not in ("usuarios", "clientes", "agenda", "clinica", "vacunacion"):
                continue
            with self.subTest(modelo=modelo.__name__):
                lista = self.client.get(reverse(f"admin:{app}_{nombre}_changelist"))
                self.assertEqual(lista.status_code, 200, f"lista de {modelo.__name__}")
                if ma.has_add_permission(_Peticion(self.admin)):
                    self.assertEqual(self.client.get(reverse(f"admin:{app}_{nombre}_add")).status_code, 200, f"alta de {modelo.__name__}")
                objeto = modelo.objects.first()
                if objeto is not None:
                    detalle = self.client.get(reverse(f"admin:{app}_{nombre}_change", args=[objeto.pk]))
                    self.assertEqual(detalle.status_code, 200, f"detalle de {modelo.__name__}")

    def test_marca_y_textos_en_espanol(self):
        portada = self.client.get(reverse("admin:index"))
        self.assertContains(portada, "PetCare")
        self.assertContains(portada, "Gestión de la clínica veterinaria")
        self.assertContains(portada, "petcare_admin.css")
        self.assertEqual(admin.site.site_header, "Administración de PetCare")
        self.assertEqual(admin.site.site_title, "PetCare · Administración")
        self.assertEqual(admin.site.index_title, "Gestión de la clínica veterinaria")

    def test_la_lista_de_citas_muestra_insignias_con_color(self):
        r = self.client.get(reverse("admin:agenda_cita_changelist"))
        self.assertContains(r, 'class="pc-insignia pc-programada"')

    def test_las_insignias_escapan_html(self):
        self.mascota.nombre = "<script>alert(1)</script>"
        self.mascota.save()
        r = self.client.get(reverse("admin:clientes_mascota_changelist"))
        self.assertNotContains(r, "<script>alert(1)</script>")

    def test_solo_el_administrador_entra_al_admin(self):
        for rol in (Rol.RECEPCIONISTA, Rol.VETERINARIO, Rol.TUTOR):
            self.client.logout()
            self.client.force_login(crear_usuario(f"u_{rol}", rol))
            r = self.client.get(reverse("admin:index"))
            self.assertEqual(r.status_code, 302, rol)
            self.assertIn("/admin/login/", r["Location"])

    def test_accion_masiva_confirma_citas(self):
        r = self.client.post(reverse("admin:agenda_cita_changelist"), {
            "action": "confirmar", "_selected_action": [self.cita.pk],
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.estado, EstadoCita.CONFIRMADA)
        self.assertEqual(self.cita.historial.last().estado_nuevo, EstadoCita.CONFIRMADA)

    def test_accion_masiva_respeta_las_transiciones(self):
        servicios_agenda.cambiar_estado(self.cita, EstadoCita.CANCELADA, usuario=self.admin)
        r = self.client.post(reverse("admin:agenda_cita_changelist"), {
            "action": "confirmar", "_selected_action": [self.cita.pk],
        }, follow=True)
        self.assertContains(r, "Transición no permitida")
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.estado, EstadoCita.CANCELADA)

    def test_el_estado_de_la_cita_no_se_edita_a_mano(self):
        r = self.client.get(reverse("admin:agenda_cita_change", args=[self.cita.pk]))
        self.assertNotContains(r, 'name="estado"')

    def test_el_admin_no_permite_crear_citas_que_se_solapan(self):
        datos = {
            "mascota": self.mascota.pk, "profesional": self.prof.pk,
            "inicio_0": self.dia.isoformat(), "inicio_1": "10:00:00",
            "fin_0": self.dia.isoformat(), "fin_1": "10:30:00", "motivo": "Duplicada",
            "historial-TOTAL_FORMS": "0", "historial-INITIAL_FORMS": "0",
        }
        r = self.client.post(reverse("admin:agenda_cita_add"), datos)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "ya tiene una cita")
        self.assertEqual(Cita.objects.count(), 1)

    def test_atenciones_son_de_solo_lectura_y_no_se_borran(self):
        url_agregar = reverse("admin:clinica_atencion_add")
        self.assertEqual(self.client.get(url_agregar).status_code, 403)
        r = self.client.post(reverse("admin:clinica_atencion_delete", args=[self.atencion.pk]), {"post": "yes"})
        self.assertEqual(r.status_code, 403)
        self.assertTrue(type(self.atencion).objects.filter(pk=self.atencion.pk).exists())

    def test_detalle_de_examen_enlaza_a_la_vista_protegida(self):
        examen = self.atencion.examenes.get()
        r = self.client.get(reverse("admin:clinica_examen_change", args=[examen.pk]))
        self.assertContains(r, reverse("examen_archivo", args=[examen.pk]))
        self.assertNotContains(r, "/media/")

    def test_mascota_con_historial_no_se_puede_eliminar_desde_el_admin(self):
        r = self.client.post(reverse("admin:clientes_mascota_delete", args=[self.mascota.pk]), {"post": "yes"})
        self.assertEqual(r.status_code, 403)

    def test_accion_desactivar_mascotas(self):
        self.client.post(reverse("admin:clientes_mascota_changelist"), {"action": "desactivar", "_selected_action": [self.mascota.pk]})
        self.mascota.refresh_from_db()
        self.assertFalse(self.mascota.activa)

    def test_accion_completar_recordatorios(self):
        ids = list(Recordatorio.objects.values_list("pk", flat=True))
        self.client.post(reverse("admin:vacunacion_recordatorio_changelist"), {"action": "completar", "_selected_action": ids})
        self.assertFalse(Recordatorio.objects.exclude(estado="COMPLETADO").exists())

    def test_accion_marcar_control_realizado(self):
        control = ControlPeriodico.objects.get()
        self.client.post(reverse("admin:vacunacion_controlperiodico_changelist"), {"action": "marcar_realizado", "_selected_action": [control.pk]})
        control.refresh_from_db()
        self.assertTrue(control.realizado)

    def test_is_staff_es_de_solo_lectura_en_el_admin_de_usuarios(self):
        r = self.client.get(reverse("admin:usuarios_usuario_change", args=[self.recep.pk]))
        self.assertNotContains(r, 'name="is_staff"')


class _Peticion:
    """Mínimo necesario para consultar has_add_permission fuera de una petición real."""

    def __init__(self, usuario):
        self.user = usuario
