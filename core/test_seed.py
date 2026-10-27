# ============================================================
# CORE/TEST_SEED.PY / EL SEED ES IDEMPOTENTE Y DEJA CREDENCIALES QUE FUNCIONAN
# ============================================================
import shutil
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from agenda.models import Cita, EstadoCita, Profesional
from clientes.models import Mascota, Tutor
from clinica.models import Atencion, Examen, Receta
from usuarios.models import Rol, Usuario
from vacunacion.models import Recordatorio, RegistroVacuna


def contar():
    modelos = (Usuario, Tutor, Mascota, Cita, Atencion, Receta, Examen, RegistroVacuna, Recordatorio)
    return {m.__name__: m.objects.count() for m in modelos}


class SeedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.carpeta = tempfile.mkdtemp()
        cls.addClassCleanup(shutil.rmtree, cls.carpeta, ignore_errors=True)
        cfg = override_settings(ARCHIVOS_PRIVADOS_ROOT=Path(cls.carpeta))
        cfg.enable()
        cls.addClassCleanup(cfg.disable)
        cls.salida = StringIO()
        call_command("seed_data", stdout=cls.salida)
        cls.primera = contar()

    def test_contenido_pedido(self):
        self.assertEqual(Usuario.objects.filter(rol=Rol.ADMINISTRADOR).count(), 1)
        self.assertEqual(Usuario.objects.filter(rol=Rol.RECEPCIONISTA).count(), 1)
        self.assertEqual(Usuario.objects.filter(rol=Rol.VETERINARIO).count(), 2)
        self.assertEqual(Tutor.objects.count(), 3)
        for tutor in Tutor.objects.all():
            self.assertEqual(tutor.mascotas.count(), 2)
        self.assertTrue(all(p.disponibilidades.exists() for p in Profesional.objects.all()))

    def test_hay_citas_pasadas_atendidas_con_ficha_completa_y_futuras(self):
        atendidas = Cita.objects.filter(estado=EstadoCita.ATENDIDA)
        self.assertGreaterEqual(atendidas.count(), 5)
        self.assertTrue(all(hasattr(c, "atencion") for c in atendidas))
        self.assertGreaterEqual(Receta.objects.count(), 4)
        self.assertGreaterEqual(Examen.objects.exclude(archivo="").count(), 2)
        futuras = Cita.objects.filter(estado__in=[EstadoCita.PROGRAMADA, EstadoCita.CONFIRMADA])
        self.assertGreaterEqual(futuras.count(), 5)

    def test_proximas_dosis_variadas_y_recordatorios_generados(self):
        from django.utils import timezone

        hoy = timezone.localdate()
        dias = [(r.proxima_dosis - hoy).days for r in RegistroVacuna.objects.all()]
        self.assertTrue(any(d < 0 for d in dias), "alguna vencida")
        self.assertTrue(any(0 <= d <= 7 for d in dias), "alguna en 7 días")
        self.assertTrue(any(8 <= d <= 30 for d in dias), "alguna en 30 días")
        self.assertTrue(Recordatorio.objects.filter(estado="VENCIDO").exists())
        self.assertTrue(Recordatorio.objects.filter(estado="PENDIENTE").exists())

    def test_es_idempotente(self):
        call_command("seed_data", stdout=StringIO())
        call_command("seed_data", stdout=StringIO())
        self.assertEqual(contar(), self.primera)

    def test_imprime_las_credenciales_y_funcionan(self):
        texto = self.salida.getvalue()
        credenciales = {
            "admin": "Admin#2026Pet", "recepcion": "Recep#2026Pet", "dra.munoz": "Vet#2026Pet",
            "dr.fuentes": "Vet#2026Pet", "carolina.rojas": "Tutor#2026Pet",
        }
        for usuario, clave in credenciales.items():
            self.assertIn(usuario, texto)
            self.assertIn(clave, texto)
            self.client.logout()
            self.assertTrue(self.client.login(username=usuario, password=clave), usuario)
            self.assertEqual(self.client.get(reverse("inicio")).status_code, 200, usuario)

    def test_las_credenciales_se_restablecen_en_cada_ejecucion(self):
        usuario = Usuario.objects.get(username="admin")
        usuario.set_password("otra-clave-distinta-9")
        usuario.save()
        call_command("seed_data", stdout=StringIO())
        self.assertTrue(self.client.login(username="admin", password="Admin#2026Pet"))

    def test_cada_tutor_demo_ve_solo_lo_suyo(self):
        self.client.login(username="carolina.rojas", password="Tutor#2026Pet")
        propias = set(Mascota.objects.filter(tutor__usuario__username="carolina.rojas").values_list("pk", flat=True))
        ajena = Mascota.objects.exclude(pk__in=propias).first()
        self.assertEqual(self.client.get(reverse("mascota_detalle", args=[ajena.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("ficha_detalle", args=[ajena.pk])).status_code, 404)
