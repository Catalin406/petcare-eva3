# ============================================================
# AGENDA/SERIALIZERS.PY / SERIALIZERS DE LA API DE AGENDA
# Crear y reprogramar citas pasa por servicios.py: la API y la web
# comparten exactamente las mismas reglas.
# ============================================================
from django.core.exceptions import ValidationError as ErrorDjango
from rest_framework import serializers

from clientes.models import Mascota
from clientes.servicios import mascotas_visibles
from usuarios.models import Rol, Usuario

from . import servicios
from .models import BloqueoAgenda, Cita, DisponibilidadSemanal, HistorialCita, Profesional


class ProfesionalSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(read_only=True)
    usuario = serializers.PrimaryKeyRelatedField(queryset=Usuario.objects.filter(rol=Rol.VETERINARIO))

    class Meta:
        model = Profesional
        fields = ["id", "usuario", "nombre", "especialidad", "activo"]


class HorarioSerializer(serializers.Serializer):
    """Un bloque de un día: libre, ocupado, bloqueado o pasado (sin datos de la cita)."""

    inicio = serializers.DateTimeField()
    fin = serializers.DateTimeField()
    hora_inicio = serializers.CharField()
    hora_fin = serializers.CharField()
    estado = serializers.ChoiceField(choices=["LIBRE", "OCUPADO", "BLOQUEADO", "PASADO"])


class DisponibilidadSerializer(serializers.ModelSerializer):
    profesional_nombre = serializers.CharField(source="profesional.nombre", read_only=True)

    class Meta:
        model = DisponibilidadSemanal
        fields = ["id", "profesional", "profesional_nombre", "dia_semana", "hora_inicio", "hora_fin", "duracion_bloque_min"]
        extra_kwargs = {"profesional": {"required": False}}
        # Sin el validador automático de unicidad (exigiría "profesional" en el cuerpo): el
        # solape lo valida el servicio y la restricción única queda en la base de datos.
        validators = []

    def validate(self, datos):
        instancia = self.instance or DisponibilidadSemanal()
        for campo, valor in datos.items():
            setattr(instancia, campo, valor)
        if "profesional" not in datos and self.instance is None:
            # El veterinario no envía profesional: la vista lo completa con el suyo.
            instancia.profesional = self.context["profesional_propio"]
        try:
            servicios.validar_disponibilidad(instancia)
        except ErrorDjango as error:
            raise serializers.ValidationError(error.messages)
        return datos


class BloqueoSerializer(serializers.ModelSerializer):
    profesional_nombre = serializers.CharField(source="profesional.nombre", read_only=True)

    class Meta:
        model = BloqueoAgenda
        fields = ["id", "profesional", "profesional_nombre", "inicio", "fin", "motivo"]
        extra_kwargs = {"profesional": {"required": False}}

    def validate(self, datos):
        inicio = datos.get("inicio", getattr(self.instance, "inicio", None))
        fin = datos.get("fin", getattr(self.instance, "fin", None))
        if inicio and fin and fin <= inicio:
            raise serializers.ValidationError("El fin del bloqueo debe ser posterior a su inicio.")
        return datos


class MascotaVisibleField(serializers.PrimaryKeyRelatedField):
    """Solo acepta mascotas que el usuario puede ver: una ajena responde "no existe"."""

    def get_queryset(self):
        return mascotas_visibles(self.context["request"].user)


class CitaSerializer(serializers.ModelSerializer):
    mascota = MascotaVisibleField()
    mascota_nombre = serializers.CharField(source="mascota.nombre", read_only=True)
    profesional_nombre = serializers.CharField(source="profesional.nombre", read_only=True)
    profesional = serializers.PrimaryKeyRelatedField(queryset=Profesional.objects.filter(activo=True))
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    # El término es opcional: si no viene, dura lo que el bloque donde empieza.
    fin = serializers.DateTimeField(required=False)

    class Meta:
        model = Cita
        fields = [
            "id", "mascota", "mascota_nombre", "profesional", "profesional_nombre", "inicio", "fin",
            "motivo", "estado", "estado_display", "creada_por", "creada_en",
        ]
        read_only_fields = ["estado", "creada_por", "creada_en"]

    def create(self, datos):
        return servicios.crear_cita(
            mascota=datos["mascota"], profesional=datos["profesional"], inicio=datos["inicio"],
            fin=datos.get("fin"), motivo=datos["motivo"], creada_por=self.context["request"].user,
        )

    def update(self, cita, datos):
        return servicios.reprogramar_cita(
            cita, usuario=self.context["request"].user, inicio=datos.get("inicio", cita.inicio),
            fin=datos.get("fin"), profesional=datos.get("profesional"), motivo=datos.get("motivo"),
        )


class CambioEstadoSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(choices=["CONFIRMADA", "CANCELADA", "NO_ASISTIO"])
    comentario = serializers.CharField(required=False, allow_blank=True, max_length=200)


class HistorialCitaSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source="usuario.nombre_visible", read_only=True, default=None)

    class Meta:
        model = HistorialCita
        fields = ["id", "estado_anterior", "estado_nuevo", "usuario_nombre", "fecha", "comentario"]
