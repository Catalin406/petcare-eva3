# ============================================================
# VACUNACION/FORMS.PY / FORMULARIOS DE VACUNAS, APLICACIONES Y CONTROLES
# ============================================================
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

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

    def __init__(self, *args, usuario, registro=None, **kwargs):
        self.usuario = usuario
        self.registro = registro
        if registro is not None:
            kwargs.setdefault("initial", {}).update(
                mascota=registro.mascota_id, vacuna=registro.vacuna_id,
                fecha_aplicacion=registro.fecha_aplicacion, lote=registro.lote,
            )
        super().__init__(*args, **kwargs)
        if registro is None:
            self.fields["mascota"].queryset = mascotas_visibles(usuario).filter(activa=True)
        else:
            # Al corregir, la mascota no cambia; la vacuna actual sigue disponible aunque ya esté desactivada.
            self.fields["mascota"].queryset = mascotas_visibles(usuario)
            self.fields["mascota"].disabled = True
            self.fields["vacuna"].queryset = Vacuna.objects.filter(Q(activa=True) | Q(pk=registro.vacuna_id))

    def guardar(self):
        d = self.cleaned_data
        try:
            if self.registro is not None:
                return servicios.actualizar_registro_vacuna(
                    self.registro, vacuna=d["vacuna"], fecha_aplicacion=d["fecha_aplicacion"], lote=d["lote"],
                    usuario=self.usuario,
                )
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
