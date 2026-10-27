# ============================================================
# API_URLS.PY / ROUTER DE LA API REST (bajo /api/)
# Cada ViewSet se registra una vez; el router genera las rutas CRUD.
# ============================================================
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from agenda.api import BloqueoViewSet, CitaViewSet, DisponibilidadViewSet, EventosAgendaView, ProfesionalViewSet
from clientes.api import MascotaViewSet, TutorViewSet
from clinica.api import AtencionViewSet, ExamenViewSet, FichaClinicaViewSet, RecetaViewSet
from vacunacion.api import ControlPeriodicoViewSet, RecordatorioViewSet, RegistroVacunaViewSet, VacunaViewSet

router = DefaultRouter()
router.register("tutores", TutorViewSet, basename="tutor")
router.register("mascotas", MascotaViewSet, basename="mascota")
router.register("profesionales", ProfesionalViewSet, basename="profesional")
router.register("disponibilidades", DisponibilidadViewSet, basename="disponibilidad")
router.register("bloqueos", BloqueoViewSet, basename="bloqueo")
router.register("citas", CitaViewSet, basename="cita")
router.register("fichas", FichaClinicaViewSet, basename="ficha")
router.register("atenciones", AtencionViewSet, basename="atencion")
router.register("recetas", RecetaViewSet, basename="receta")
router.register("examenes", ExamenViewSet, basename="examen")
router.register("vacunas", VacunaViewSet, basename="vacuna")
router.register("registros-vacuna", RegistroVacunaViewSet, basename="registro-vacuna")
router.register("controles", ControlPeriodicoViewSet, basename="control")
router.register("recordatorios", RecordatorioViewSet, basename="recordatorio")

urlpatterns = [
    path("agenda/eventos/", EventosAgendaView.as_view(), name="agenda-eventos"),
    path("", include(router.urls)),
]
