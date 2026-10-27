# ============================================================
# CLIENTES/API.PY / VIEWSETS DE TUTORES Y MASCOTAS
# ============================================================
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.archivos import entregar_archivo
from core.permisos_api import STAFF, TODOS, PorRol
from usuarios.models import Rol

from . import servicios
from .models import Mascota, Tutor
from .serializers import MascotaSerializer, TutorSerializer


class TutorViewSet(viewsets.ModelViewSet):
    """Tutores. Staff: CRUD. Tutor: solo su propio registro (lectura)."""

    queryset = Tutor.objects.none()  # solo para el esquema OpenAPI; get_queryset() filtra por usuario
    serializer_class = TutorSerializer
    permission_classes = [PorRol]
    roles_lectura = STAFF + (Rol.TUTOR,)
    roles_escritura = STAFF
    filterset_fields = ["telefono"]
    search_fields = ["rut", "usuario__first_name", "usuario__last_name", "usuario__email"]
    ordering_fields = ["usuario__last_name", "rut", "creado_en"]

    def get_queryset(self):
        return servicios.tutores_visibles(self.request.user)

    def destroy(self, request, *args, **kwargs):
        resultado = servicios.eliminar_o_desactivar_tutor(self.get_object())
        codigo = status.HTTP_204_NO_CONTENT if resultado == "eliminado" else status.HTTP_200_OK
        return Response({"resultado": resultado} if codigo == 200 else None, status=codigo)


class MascotaViewSet(viewsets.ModelViewSet):
    """Mascotas. Staff: CRUD. Veterinario: lectura. Tutor: lectura de las suyas."""

    queryset = Mascota.objects.none()  # solo para el esquema OpenAPI; get_queryset() filtra por usuario
    serializer_class = MascotaSerializer
    permission_classes = [PorRol]
    roles_lectura = TODOS
    roles_escritura = STAFF
    roles_acciones = {"foto": TODOS}
    filterset_fields = ["especie", "sexo", "activa", "tutor"]
    search_fields = ["nombre", "raza", "microchip", "tutor__rut", "tutor__usuario__last_name"]
    ordering_fields = ["nombre", "fecha_nacimiento", "creada_en"]

    def get_queryset(self):
        return servicios.mascotas_visibles(self.request.user)

    def destroy(self, request, *args, **kwargs):
        resultado = servicios.eliminar_o_desactivar_mascota(self.get_object())
        codigo = status.HTTP_204_NO_CONTENT if resultado == "eliminada" else status.HTTP_200_OK
        return Response({"resultado": resultado} if codigo == 200 else None, status=codigo)

    @action(detail=True, methods=["get"], url_path="foto")
    def foto(self, request, pk=None):
        """Entrega la foto (binario). Requiere JWT y permiso sobre la mascota."""
        return entregar_archivo(self.get_object().foto)
