# ============================================================
# CLIENTES/FORMS.PY / FORMULARIOS DE TUTOR Y MASCOTA
# El formulario de tutor junta los datos de la cuenta (Usuario) y los
# del tutor; el guardado real lo hace servicios.py.
# ============================================================
from django import forms
from django.core.exceptions import ValidationError

from core.forms import FormularioBase, FormularioModeloBase, volcar_errores
from core.validadores import normalizar_rut, validar_rut
from usuarios.models import Usuario

from . import servicios
from .models import Mascota, Tutor


class TutorForm(FormularioBase):
    username = forms.CharField(label="Usuario", max_length=150)
    password = forms.CharField(
        label="Contraseña inicial", widget=forms.PasswordInput(render_value=False), required=False,
        help_text="Mínimo 10 caracteres. Solo se pide al crear el tutor.",
    )
    first_name = forms.CharField(label="Nombre", max_length=150)
    last_name = forms.CharField(label="Apellidos", max_length=150)
    email = forms.EmailField(label="Correo", help_text="Aquí se envían los recordatorios de vacunas y controles.")
    rut = forms.CharField(label="RUT", max_length=12, help_text="Con o sin puntos y guion. Ej.: 12.345.678-5")
    telefono = forms.CharField(label="Teléfono", max_length=16)
    direccion = forms.CharField(label="Dirección", max_length=200)

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None:
            kwargs.setdefault("initial", {}).update(
                username=instance.usuario.username, first_name=instance.usuario.first_name,
                last_name=instance.usuario.last_name, email=instance.usuario.email,
                rut=instance.rut, telefono=instance.telefono, direccion=instance.direccion,
            )
        super().__init__(*args, **kwargs)
        if instance is not None:
            # El usuario y la clave no se cambian desde esta pantalla.
            del self.fields["password"]
            self.fields["username"].disabled = True
        else:
            self.fields["password"].required = True

    def clean_rut(self):
        rut = normalizar_rut(self.cleaned_data["rut"])
        validar_rut(rut)
        repetidos = Tutor.objects.filter(rut=rut)
        if self.instance is not None:
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise ValidationError("Ya existe un tutor con ese RUT.")
        return rut

    def clean_username(self):
        username = self.cleaned_data["username"]
        if self.instance is None and Usuario.objects.filter(username__iexact=username).exists():
            raise ValidationError("Ese nombre de usuario ya está en uso.")
        return username

    def guardar(self):
        """Devuelve el Tutor, o None si el servicio rechazó algo (error ya cargado en el formulario)."""
        d = self.cleaned_data
        try:
            if self.instance is not None:
                return servicios.actualizar_tutor(
                    self.instance, first_name=d["first_name"], last_name=d["last_name"], email=d["email"],
                    rut=d["rut"], telefono=d["telefono"], direccion=d["direccion"],
                )
            return servicios.crear_tutor(
                username=d["username"], password=d["password"], first_name=d["first_name"],
                last_name=d["last_name"], email=d["email"], rut=d["rut"], telefono=d["telefono"],
                direccion=d["direccion"],
            )
        except ValidationError as error:
            volcar_errores(self, error)
            return None


class MascotaForm(FormularioModeloBase):
    class Meta:
        model = Mascota
        fields = [
            "tutor", "nombre", "especie", "raza", "sexo", "fecha_nacimiento", "peso",
            "color_senas", "microchip", "foto", "activa",
        ]
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            # FileInput (no ClearableFileInput): este último intenta mostrar foto.url,
            # y los archivos privados no tienen URL pública.
            "foto": forms.FileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tutor"].queryset = Tutor.objects.select_related("usuario").filter(usuario__is_active=True)
