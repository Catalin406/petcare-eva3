# ============================================================
# VACUNACION/SERIALIZERS.PY / SERIALIZERS DE LA API
# ============================================================
from django.core.exceptions import ValidationError as ErrorDjango
from rest_framework import serializers

from agenda.models import Profesional
from clientes.servicios import mascotas_visibles

from . import servicios
from .models import ControlPeriodico, Recordatorio, RegistroVacuna, Vacuna


class VacunaSerializer(serializers.ModelSerializer):
    especie_display = serializers.CharField(source="get_especie_aplicable_display", read_only=True)

    class Meta:
        model = Vacuna
        fields = ["id", "nombre", "especie_aplicable", "especie_display", "periodicidad_dias", "activa"]


class _MascotaVisibleField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return mascotas_visibles(self.context["request"].user)


class RegistroVacunaSerializer(serializers.ModelSerializer):
    mascota = _MascotaVisibleField()
    mascota_nombre = serializers.CharField(source="mascota.nombre", read_only=True)
    vacuna_nombre = serializers.CharField(source="vacuna.nombre", read_only=True)
    veterinario = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = RegistroVacuna
        fields = [
            "id", "mascota", "mascota_nombre", "vacuna", "vacuna_nombre", "fecha_aplicacion", "lote",
            "veterinario", "proxima_dosis",
        ]
        read_only_fields = ["proxima_dosis"]

    def create(self, datos):
        return servicios.registrar_vacuna(
            mascota=datos["mascota"], vacuna=datos["vacuna"], fecha_aplicacion=datos["fecha_aplicacion"],
            lote=datos.get("lote", ""), usuario=self.context["request"].user,
        )

    def update(self, registro, datos):
        for campo in ("fecha_aplicacion", "lote", "vacuna"):
            if campo in datos:
                setattr(registro, campo, datos[campo])
        registro.proxima_dosis = registro.calcular_proxima_dosis()
        try:
            registro.full_clean()
        except ErrorDjango as error:
            raise serializers.ValidationError(error.message_dict)
        registro.save()
        return registro


class ControlSerializer(serializers.ModelSerializer):
    mascota = _MascotaVisibleField()
    mascota_nombre = serializers.CharField(source="mascota.nombre", read_only=True)

    class Meta:
        model = ControlPeriodico
        fields = ["id", "mascota", "mascota_nombre", "motivo", "fecha_programada", "realizado"]


class RecordatorioSerializer(serializers.ModelSerializer):
    mascota_nombre = serializers.CharField(source="mascota.nombre", read_only=True)
    descripcion = serializers.CharField(read_only=True)
    dias_restantes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Recordatorio
        fields = [
            "id", "mascota", "mascota_nombre", "tipo", "descripcion", "fecha_objetivo", "dias_restantes",
            "estado", "canal", "enviado_en",
        ]
        read_only_fields = fields


class PanelRecordatoriosSerializer(serializers.Serializer):
    vencidos = RecordatorioSerializer(many=True)
    semana = RecordatorioSerializer(many=True)
    mes = RecordatorioSerializer(many=True)
