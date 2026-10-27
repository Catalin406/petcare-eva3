# ============================================================
# CLINICA/SERIALIZERS.PY / SERIALIZERS DE LA FICHA CLÍNICA
# Los adjuntos de exámenes se exponen como URL de la acción protegida
# /api/examenes/{id}/archivo/ (JWT + permisos), nunca como ruta de media.
# ============================================================
from rest_framework import serializers
from rest_framework.reverse import reverse

from agenda.models import Cita, Profesional
from usuarios.models import Rol

from . import servicios
from .models import Atencion, Examen, FichaClinica, Receta


class FichaClinicaSerializer(serializers.ModelSerializer):
    mascota_nombre = serializers.CharField(source="mascota.nombre", read_only=True)

    class Meta:
        model = FichaClinica
        fields = ["id", "mascota", "mascota_nombre", "alergias", "antecedentes", "observaciones", "actualizada_en"]
        read_only_fields = ["mascota", "actualizada_en"]

    def update(self, ficha, datos):
        return servicios.actualizar_ficha(
            ficha, usuario=self.context["request"].user,
            alergias=datos.get("alergias", ficha.alergias),
            antecedentes=datos.get("antecedentes", ficha.antecedentes),
            observaciones=datos.get("observaciones", ficha.observaciones),
        )


class RecetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receta
        fields = ["id", "atencion", "medicamento", "dosis", "frecuencia", "duracion", "indicaciones"]

    def get_fields(self):
        campos = super().get_fields()
        campos["atencion"] = AtencionPropiaField()
        return campos


class RecetaAnidadaSerializer(serializers.ModelSerializer):
    """Receta dentro de una atención (el id de la atención se asigna al guardar)."""

    class Meta:
        model = Receta
        fields = ["id", "medicamento", "dosis", "frecuencia", "duracion", "indicaciones"]


class AtencionPropiaField(serializers.PrimaryKeyRelatedField):
    """Solo se puede agregar contenido a atenciones escritas por el propio veterinario."""

    def get_queryset(self):
        usuario = self.context["request"].user
        return servicios.atenciones_visibles(usuario).filter(veterinario__usuario=usuario)


class ExamenSerializer(serializers.ModelSerializer):
    archivo = serializers.FileField(write_only=True, required=False, allow_null=True)
    archivo_url = serializers.SerializerMethodField()

    class Meta:
        model = Examen
        fields = ["id", "atencion", "tipo", "fecha", "resultado", "archivo", "archivo_url"]

    def get_fields(self):
        campos = super().get_fields()
        campos["atencion"] = AtencionPropiaField()
        return campos

    def get_archivo_url(self, examen) -> str | None:
        if not examen.archivo:
            return None
        return reverse("examen-archivo", args=[examen.pk], request=self.context.get("request"))

    def validate(self, datos):
        # Reutiliza los validadores del modelo (extensión y tamaño del adjunto).
        from django.core.exceptions import ValidationError

        examen = Examen(**{k: v for k, v in datos.items()})
        try:
            examen.full_clean(exclude=["atencion"])
        except ValidationError as error:
            raise serializers.ValidationError(error.message_dict)
        return datos


class ExamenLecturaSerializer(serializers.ModelSerializer):
    archivo_url = serializers.SerializerMethodField()

    class Meta:
        model = Examen
        fields = ["id", "tipo", "fecha", "resultado", "archivo_url"]

    def get_archivo_url(self, examen) -> str | None:
        if not examen.archivo:
            return None
        return reverse("examen-archivo", args=[examen.pk], request=self.context.get("request"))


class AtencionSerializer(serializers.ModelSerializer):
    mascota_nombre = serializers.CharField(source="ficha.mascota.nombre", read_only=True)
    veterinario_nombre = serializers.CharField(source="veterinario.nombre", read_only=True)
    recetas = RecetaAnidadaSerializer(many=True, required=False)
    examenes = ExamenLecturaSerializer(many=True, read_only=True)

    class Meta:
        model = Atencion
        fields = [
            "id", "ficha", "mascota_nombre", "cita", "veterinario", "veterinario_nombre", "fecha", "anamnesis",
            "peso_kg", "temperatura_c", "diagnostico", "tratamiento", "observaciones", "recetas", "examenes",
        ]
        read_only_fields = ["veterinario"]
        extra_kwargs = {"ficha": {"required": False}}

    def get_fields(self):
        campos = super().get_fields()
        usuario = self.context["request"].user
        campos["ficha"].queryset = servicios.fichas_visibles(usuario)
        campos["cita"].queryset = Cita.objects.filter(profesional__usuario=usuario)
        return campos

    def create(self, datos):
        recetas = datos.pop("recetas", [])
        ficha, cita = datos.pop("ficha", None), datos.pop("cita", None)
        if ficha is None and cita is not None:
            ficha = cita.mascota.ficha
        if ficha is None:
            raise serializers.ValidationError({"ficha": "Indica la ficha (o la cita que se atiende)."})
        return servicios.registrar_atencion(
            veterinario=Profesional.objects.get(usuario=self.context["request"].user),
            ficha=ficha, cita=cita, datos=datos, recetas=[dict(r) for r in recetas],
        )

    def update(self, atencion, datos):
        recetas = datos.pop("recetas", [])
        datos.pop("ficha", None)
        datos.pop("cita", None)
        return servicios.actualizar_atencion(
            atencion, usuario=self.context["request"].user, datos=datos, recetas=[dict(r) for r in recetas]
        )
