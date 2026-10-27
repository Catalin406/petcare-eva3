# ============================================================
# VACUNACION/FORMS.PY / FORMULARIOS DE VACUNAS, APLICACIONES Y CONTROLES
# ============================================================
from django import forms
from django.core.exceptions import ValidationError

from clientes.servicios import mascotas_visibles
from core.forms import FormularioBase, FormularioModeloBase, volcar_errores

from . import servicios
from .models import ControlPeriodico, Vacuna


class VacunaForm(FormularioModeloBase):
    class Meta:
        model = Vacuna
        fields = ["nombre", "especie_aplicable", "periodicidad_dias", "activa"]


class RegistroVacunaForm(FormularioBase):
    mascota = forms.ModelChoiceField(queryset=None, label="Mascota")
    vacuna = forms.ModelChoiceField(queryset=Vacuna.objects.filter(activa=True), label="Vacuna")
    fecha_aplicacion = forms.DateField(label="Fecha de aplicación", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    lote = forms.CharField(label="Lote", max_length=40, required=False)

    def __init__(self, *args, usuario, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)
        self.fields["mascota"].queryset = mascotas_visibles(usuario).filter(activa=True)

    def guardar(self):
        d = self.cleaned_data
        try:
            return servicios.registrar_vacuna(
                mascota=d["mascota"], vacuna=d["vacuna"], fecha_aplicacion=d["fecha_aplicacion"],
                lote=d["lote"], usuario=self.usuario,
            )
        except ValidationError as error:
            volcar_errores(self, error)
            return None


class ControlForm(FormularioModeloBase):
    class Meta:
        model = ControlPeriodico
        fields = ["mascota", "motivo", "fecha_programada", "realizado"]
        widgets = {"fecha_programada": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mascota"].queryset = mascotas_visibles(usuario).filter(activa=True)
