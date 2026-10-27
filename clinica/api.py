# ============================================================
# CLINICA/API.PY / VIEWSETS DE LA FICHA CLÍNICA
# Sin DELETE en atenciones, recetas ni exámenes: es un registro clínico.
# Recepción no tiene acceso. El tutor solo lee lo de SUS mascotas.
# ============================================================
from rest_framework import mixins, viewsets
from rest_framework.decorators import action

from core.archivos import entregar_archivo
from core.permisos_api import PorRol
from usuarios.models import Rol

from . import servicios
from .models import Atencion, Examen, FichaClinica, Receta
from .serializers import (
    AtencionSerializer, ExamenSerializer, FichaClinicaSerializer, RecetaSerializer,
)

ADMIN_VET = (Rol.ADMINISTRADOR, Rol.VETERINARIO)


class FichaClinicaViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Fichas clínicas (se crean solas con la mascota). Lectura: admin, vet y tutor propio."""

    queryset = FichaClinica.objects.none()  # solo para el esquema OpenAPI
    serializer_class = FichaClinicaSerializer
    permission_classes = [PorRol]
    roles_lectura = servicios.ROLES_CLINICOS
    roles_escritura = ADMIN_VET
    filterset_fields = ["mascota"]
    search_fields = ["mascota__nombre", "alergias"]

    def get_queryset(self):
        return servicios.fichas_visibles(self.request.user)


class AtencionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                      mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Atenciones. Solo el VETERINARIO crea o corrige las suyas; no existe DELETE."""

    queryset = Atencion.objects.none()  # solo para el esquema OpenAPI
    serializer_class = AtencionSerializer
    permission_classes = [PorRol]
    roles_lectura = servicios.ROLES_CLINICOS
    roles_escritura = (Rol.VETERINARIO,)
    filterset_fields = ["ficha", "ficha__mascota", "veterinario"]
    search_fields = ["diagnostico", "anamnesis", "ficha__mascota__nombre"]
    ordering_fields = ["fecha"]
    ordering = ["-fecha"]

    def get_queryset(self):
        return servicios.atenciones_visibles(self.request.user).prefetch_related("recetas", "examenes")


class RecetaViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Recetas de las atenciones. Se agregan (VETERINARIO autor) pero no se borran."""

    queryset = Receta.objects.none()  # solo para el esquema OpenAPI
    serializer_class = RecetaSerializer
    permission_classes = [PorRol]
    roles_lectura = servicios.ROLES_CLINICOS
    roles_escritura = (Rol.VETERINARIO,)
    filterset_fields = ["atencion"]
    search_fields = ["medicamento"]

    def get_queryset(self):
        return servicios.recetas_visibles(self.request.user)


class ExamenViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Exámenes con adjunto opcional (multipart). El archivo se descarga por /archivo/."""

    queryset = Examen.objects.none()  # solo para el esquema OpenAPI
    serializer_class = ExamenSerializer
    permission_classes = [PorRol]
    roles_lectura = servicios.ROLES_CLINICOS
    roles_escritura = (Rol.VETERINARIO,)
    roles_acciones = {"archivo": servicios.ROLES_CLINICOS}
    filterset_fields = ["atencion", "tipo", "fecha"]
    search_fields = ["tipo", "resultado"]

    def get_queryset(self):
        return servicios.examenes_visibles(self.request.user)

    @action(detail=True, methods=["get"], url_path="archivo")
    def archivo(self, request, pk=None):
        """Entrega el adjunto (binario). Requiere JWT y permiso sobre la atención."""
        return entregar_archivo(self.get_object().archivo, descargar=request.query_params.get("descargar") == "1")
