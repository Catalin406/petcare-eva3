# ============================================================
# CLIENTES/SERIALIZERS.PY / SERIALIZERS DE LA API
# La foto no se expone como ruta de media: foto_url apunta a la acción
# protegida /api/mascotas/{id}/foto/ (exige JWT y permisos).
# ============================================================
from django.core.exceptions import ValidationError as ErrorDjango
from rest_framework import serializers
from rest_framework.reverse import reverse

from core.validadores import normalizar_rut, validar_rut

from . import servicios
from .models import Mascota, Tutor


class TutorSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="usuario.username", max_length=150)
    first_name = serializers.CharField(source="usuario.first_name", max_length=150)
    last_name = serializers.CharField(source="usuario.last_name", max_length=150)
    email = serializers.EmailField(source="usuario.email")
    password = serializers.CharField(write_only=True, required=False, style={"input_type": "password"})
    # Se declara explícito para validar y normalizar nosotros (puntos/guion/mayúscula).
    rut = serializers.CharField(max_length=12)
    total_mascotas = serializers.SerializerMethodField()

    class Meta:
        model = Tutor
        fields = [
            "id", "username", "password", "first_name", "last_name", "email",
            "rut", "telefono", "direccion", "total_mascotas",
        ]

    def get_total_mascotas(self, tutor) -> int:
        return tutor.mascotas.count()

    def validate_rut(self, valor):
        rut = normalizar_rut(valor)
        try:
            validar_rut(rut)
        except ErrorDjango as error:
            raise serializers.ValidationError(error.messages)
        repetidos = Tutor.objects.filter(rut=rut)
        if self.instance is not None:
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise serializers.ValidationError("Ya existe un tutor con ese RUT.")
        return rut

    def validate(self, datos):
        if self.instance is None and not self.initial_data.get("password"):
            raise serializers.ValidationError({"password": "La contraseña inicial es obligatoria al crear."})
        return datos

    def create(self, datos):
        usuario = datos.pop("usuario")
        return servicios.crear_tutor(
            username=usuario["username"], password=self.initial_data["password"],
            first_name=usuario["first_name"], last_name=usuario["last_name"], email=usuario["email"],
            rut=datos["rut"], telefono=datos["telefono"], direccion=datos["direccion"],
        )

    def update(self, tutor, datos):
        usuario = datos.pop("usuario", {})
        return servicios.actualizar_tutor(
            tutor,
            first_name=usuario.get("first_name", tutor.usuario.first_name),
            last_name=usuario.get("last_name", tutor.usuario.last_name),
            email=usuario.get("email", tutor.usuario.email),
            rut=datos.get("rut", tutor.rut),
            telefono=datos.get("telefono", tutor.telefono),
            direccion=datos.get("direccion", tutor.direccion),
        )


class MascotaSerializer(serializers.ModelSerializer):
    edad = serializers.CharField(source="edad_texto", read_only=True)
    tutor_nombre = serializers.CharField(source="tutor.nombre_completo", read_only=True)
    foto = serializers.ImageField(write_only=True, required=False, allow_null=True)
    foto_url = serializers.SerializerMethodField()

    class Meta:
        model = Mascota
        fields = [
            "id", "tutor", "tutor_nombre", "nombre", "especie", "raza", "sexo", "fecha_nacimiento",
            "edad", "peso", "color_senas", "microchip", "foto", "foto_url", "activa",
        ]

    def get_foto_url(self, mascota) -> str | None:
        if not mascota.foto:
            return None
        return reverse("mascota-foto", args=[mascota.pk], request=self.context.get("request"))

    def validate(self, datos):
        # Reutiliza las validaciones del modelo (fecha futura, microchip, nombre repetido).
        instancia = self.instance or Mascota()
        for campo, valor in datos.items():
            setattr(instancia, campo, valor)
        try:
            instancia.full_clean(exclude=["foto"] if "foto" not in datos else None)
        except ErrorDjango as error:
            raise serializers.ValidationError(error.message_dict)
        return datos
