# ============================================================
# VACUNACION/API.PY / VIEWSETS DE VACUNAS, CONTROLES Y RECORDATORIOS
# ============================================================
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permisos_api import STAFF, TODOS, PorRol
from usuarios.models import Rol

from . import servicios
from .models import Vacuna
from .serializers import (
    ControlSerializer, PanelRecordatoriosSerializer, RecordatorioSerializer, RegistroVacunaSerializer, VacunaSerializer,
)

VETERINARIA = (Rol.ADMINISTRADOR, Rol.VETERINARIO)
GESTION = (Rol.ADMINISTRADOR, Rol.VETERINARIO, Rol.RECEPCIONISTA)


class VacunaViewSet(viewsets.ModelViewSet):
    """Catálogo de vacunas. Todos leen; administrador y veterinario modifican."""

    queryset = Vacuna.objects.all()
    serializer_class = VacunaSerializer
    permission_classes = [PorRol]
    roles_lectura = TODOS
    roles_escritura = VETERINARIA
    filterset_fields = ["especie_aplicable", "activa"]
    search_fields = ["nombre"]


class RegistroVacunaViewSet(viewsets.ModelViewSet):
    """Vacunas aplicadas; la próxima dosis se calcula sola (fecha + periodicidad)."""

    serializer_class = RegistroVacunaSerializer
    permission_classes = [PorRol]
    roles_lectura = TODOS
    roles_escritura = VETERINARIA
    roles_acciones = {"destroy": (Rol.ADMINISTRADOR,)}
    filterset_fields = ["mascota", "vacuna"]
    search_fields = ["mascota__nombre", "vacuna__nombre", "lote"]
    ordering_fields = ["fecha_aplicacion", "proxima_dosis"]

    def get_queryset(self):
        return servicios.registros_vacuna_visibles(self.request.user)


class ControlPeriodicoViewSet(viewsets.ModelViewSet):
    """Controles periódicos. Recepción, veterinario y administrador gestionan; el tutor lee los suyos."""

    serializer_class = ControlSerializer
    permission_classes = [PorRol]
    roles_lectura = TODOS
    roles_escritura = GESTION
    roles_acciones = {"realizado": GESTION}
    filterset_fields = ["mascota", "realizado"]
    search_fields = ["motivo", "mascota__nombre"]
    ordering_fields = ["fecha_programada"]

    def get_queryset(self):
        return servicios.controles_visibles(self.request.user)

    @extend_schema(request=None, responses=ControlSerializer)
    @action(detail=True, methods=["post"])
    def realizado(self, request, pk=None):
        """Marca el control como realizado y cierra sus recordatorios."""
        control = servicios.marcar_control_realizado(self.get_object())
        return Response(self.get_serializer(control).data)


class RecordatorioViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Recordatorios (los crea el comando generar_recordatorios). El tutor ve solo los suyos."""

    serializer_class = RecordatorioSerializer
    permission_classes = [PorRol]
    roles_lectura = TODOS
    roles_escritura = (Rol.ADMINISTRADOR,)
    roles_acciones = {"panel": TODOS, "generar": (Rol.ADMINISTRADOR,)}
    filterset_fields = ["tipo", "estado", "mascota", "canal"]
    ordering_fields = ["fecha_objetivo"]

    def get_queryset(self):
        return servicios.recordatorios_visibles(self.request.user)

    @extend_schema(responses=PanelRecordatoriosSerializer)
    @action(detail=False, methods=["get"], pagination_class=None)
    def panel(self, request):
        """Vencidos, próximos 7 días y próximos 30 días (colores de urgencia en la web)."""
        grupos = servicios.panel_recordatorios(request.user)
        return Response(PanelRecordatoriosSerializer(grupos).data)

    @extend_schema(
        request=None,
        responses=inline_serializer("ResumenGeneracion", {
            "creados": serializers.IntegerField(), "vencidos": serializers.IntegerField(),
            "completados": serializers.IntegerField(), "enviados": serializers.IntegerField(),
            "sin_correo": serializers.IntegerField(), "errores_envio": serializers.IntegerField(),
        }),
    )
    @action(detail=False, methods=["post"])
    def generar(self, request):
        """Ejecuta generar_recordatorios desde la API (solo administrador)."""
        return Response(servicios.generar_recordatorios())
