# ============================================================
# AGENDA/API.PY / VIEWSETS DE PROFESIONALES, DISPONIBILIDAD, BLOQUEOS Y CITAS
# ============================================================
from datetime import date, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as ErrorDRF
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permisos_api import STAFF, TODOS, PorRol
from usuarios.models import Rol

from . import servicios
from .models import BloqueoAgenda, Cita, DisponibilidadSemanal, EstadoCita, Profesional
from .serializers import (
    BloqueoSerializer, CambioEstadoSerializer, CitaSerializer, DisponibilidadSerializer,
    HistorialCitaSerializer, HorarioSerializer, ProfesionalSerializer,
)


def _parsear_fecha(texto, nombre="fecha"):
    try:
        return date.fromisoformat(texto)
    except (TypeError, ValueError):
        raise ErrorDRF({nombre: "Indica la fecha en formato AAAA-MM-DD."})


class ProfesionalViewSet(viewsets.ModelViewSet):
    """Veterinarios. Todos los roles consultan; solo el administrador crea o modifica."""

    queryset = Profesional.objects.select_related("usuario")
    serializer_class = ProfesionalSerializer
    permission_classes = [PorRol]
    roles_lectura = TODOS
    roles_escritura = (Rol.ADMINISTRADOR,)
    roles_acciones = {"horarios": TODOS}
    filterset_fields = ["activo", "especialidad"]
    search_fields = ["usuario__first_name", "usuario__last_name", "especialidad"]

    @extend_schema(
        parameters=[OpenApiParameter("fecha", OpenApiTypes.DATE, required=True, description="AAAA-MM-DD")],
        responses=HorarioSerializer(many=True),
    )
    @action(detail=True, methods=["get"])
    def horarios(self, request, pk=None):
        """Bloques del día de este veterinario (libres y ocupados, sin datos de las citas)."""
        profesional = self.get_object()
        fecha = _parsear_fecha(request.query_params.get("fecha"))
        datos = [
            {
                "inicio": h.inicio, "fin": h.fin, "estado": h.estado,
                "hora_inicio": timezone.localtime(h.inicio).strftime("%H:%M"),
                "hora_fin": timezone.localtime(h.fin).strftime("%H:%M"),
            }
            for h in servicios.horarios_del_dia(profesional, fecha)
        ]
        return Response(HorarioSerializer(datos, many=True).data)


class _AgendaPropiaViewSet(viewsets.ModelViewSet):
    """Base: el veterinario solo ve y edita lo SUYO; el administrador, todo."""

    permission_classes = [PorRol]
    roles_lectura = (Rol.ADMINISTRADOR, Rol.RECEPCIONISTA, Rol.VETERINARIO)
    roles_escritura = (Rol.ADMINISTRADOR, Rol.VETERINARIO)
    modelo = None

    def get_queryset(self):
        consulta = self.modelo.objects.select_related("profesional__usuario")
        if self.request.user.rol == Rol.VETERINARIO:
            consulta = consulta.filter(profesional__usuario=self.request.user)
        return consulta

    def _profesional_propio(self):
        return Profesional.objects.filter(usuario=self.request.user).first()

    def get_serializer_context(self):
        contexto = super().get_serializer_context()
        if self.request and self.request.user.is_authenticated:
            contexto["profesional_propio"] = self._profesional_propio()
        return contexto

    def perform_create(self, serializer):
        if self.request.user.rol == Rol.VETERINARIO:
            serializer.save(profesional=self._profesional_propio())
        elif "profesional" not in serializer.validated_data:
            raise ErrorDRF({"profesional": "Indica el profesional."})
        else:
            serializer.save()

    def perform_update(self, serializer):
        # Un veterinario no puede traspasar un bloque a otro profesional.
        if self.request.user.rol == Rol.VETERINARIO:
            serializer.save(profesional=self._profesional_propio())
        else:
            serializer.save()


class DisponibilidadViewSet(_AgendaPropiaViewSet):
    """Disponibilidad semanal recurrente por profesional."""

    modelo = DisponibilidadSemanal
    serializer_class = DisponibilidadSerializer
    filterset_fields = ["profesional", "dia_semana"]
    ordering_fields = ["dia_semana", "hora_inicio"]


class BloqueoViewSet(_AgendaPropiaViewSet):
    """Bloqueos de agenda (vacaciones, feriados)."""

    modelo = BloqueoAgenda
    serializer_class = BloqueoSerializer
    filterset_fields = ["profesional"]
    ordering_fields = ["inicio"]


class CitaViewSet(viewsets.ModelViewSet):
    """
    Citas. Administrador y recepción: todo. Veterinario: su agenda (ver, confirmar).
    Tutor: ve, solicita y cancela las de SUS mascotas.
    """

    serializer_class = CitaSerializer
    permission_classes = [PorRol]
    roles_lectura = TODOS
    roles_escritura = STAFF
    roles_acciones = {
        "create": STAFF + (Rol.TUTOR,),
        "destroy": (Rol.ADMINISTRADOR,),
        "cambiar_estado": TODOS,
        "cancelar": STAFF + (Rol.TUTOR,),
        "historial": TODOS,
    }
    filterset_fields = ["estado", "profesional", "mascota"]
    search_fields = ["mascota__nombre", "motivo"]
    ordering_fields = ["inicio", "creada_en"]
    ordering = ["inicio"]

    def get_queryset(self):
        return servicios.citas_visibles(self.request.user)

    @extend_schema(request=CambioEstadoSerializer, responses=CitaSerializer)
    @action(detail=True, methods=["post"], url_path="cambiar-estado")
    def cambiar_estado(self, request, pk=None):
        """Confirma, cancela o marca inasistencia (las reglas por rol las aplica el servicio)."""
        entrada = CambioEstadoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        cita = servicios.cambiar_estado(
            self.get_object(), entrada.validated_data["estado"], usuario=request.user,
            comentario=entrada.validated_data.get("comentario", ""),
        )
        return Response(self.get_serializer(cita).data)

    @extend_schema(request=None, responses=CitaSerializer)
    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        """Atajo para cancelar la cita (el tutor lo usa con su anticipación mínima)."""
        cita = servicios.cambiar_estado(self.get_object(), EstadoCita.CANCELADA, usuario=request.user)
        return Response(self.get_serializer(cita).data)

    @extend_schema(responses=HistorialCitaSerializer(many=True))
    @action(detail=True, methods=["get"], pagination_class=None)
    def historial(self, request, pk=None):
        """Bitácora de cambios de estado de la cita."""
        return Response(HistorialCitaSerializer(self.get_object().historial.select_related("usuario"), many=True).data)


class EventosAgendaView(APIView):
    """Eventos para el calendario web (FullCalendar): bloques de un veterinario entre dos fechas."""

    permission_classes = [PorRol]
    roles_lectura = TODOS
    roles_escritura = ()

    @extend_schema(
        parameters=[
            OpenApiParameter("profesional", OpenApiTypes.INT, required=True),
            OpenApiParameter("start", OpenApiTypes.DATE, required=True, description="Desde (AAAA-MM-DD)"),
            OpenApiParameter("end", OpenApiTypes.DATE, required=True, description="Hasta (AAAA-MM-DD, exclusivo)"),
        ],
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request):
        try:
            profesional = Profesional.objects.get(pk=request.query_params.get("profesional"), activo=True)
        except (Profesional.DoesNotExist, ValueError, TypeError):
            return Response({"profesional": "Profesional no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        # Un veterinario solo consulta su propia agenda.
        if request.user.rol == Rol.VETERINARIO and profesional.usuario_id != request.user.pk:
            return Response({"detail": "Solo puedes ver tu propia agenda."}, status=status.HTTP_403_FORBIDDEN)
        desde = _parsear_fecha(request.query_params.get("start"), "start")
        hasta = _parsear_fecha(request.query_params.get("end"), "end") - timedelta(days=1)
        if (hasta - desde).days > 62:
            raise ErrorDRF({"end": "El rango máximo es de 62 días."})
        return Response(servicios.eventos_calendario(request.user, profesional, desde, hasta))
