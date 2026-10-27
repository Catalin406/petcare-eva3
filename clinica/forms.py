# ============================================================
# CLINICA/FORMS.PY / FORMULARIOS DE FICHA, ATENCIÓN, RECETAS Y EXÁMENES
# ============================================================
from datetime import timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.forms import modelformset_factory
from django.utils import timezone

from clientes.servicios import mascotas_visibles
from core.forms import EstiloBootstrapMixin, FormularioModeloBase

from .models import Atencion, Examen, FichaClinica, Receta


class FichaForm(FormularioModeloBase):
    class Meta:
        model = FichaClinica
        fields = ["alergias", "antecedentes", "observaciones"]
        widgets = {campo: forms.Textarea(attrs={"rows": 3}) for campo in fields}


class AtencionForm(FormularioModeloBase):
    # Solo se usa en urgencias (sin cita): la ficha sale de la mascota elegida.
    mascota = forms.ModelChoiceField(queryset=None, required=False, label="Mascota (urgencia sin cita)")

    class Meta:
        model = Atencion
        fields = ["fecha", "anamnesis", "peso_kg", "temperatura_c", "diagnostico", "tratamiento", "observaciones"]
        widgets = {
            "fecha": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "anamnesis": forms.Textarea(attrs={"rows": 3}),
            "diagnostico": forms.Textarea(attrs={"rows": 3}),
            "tratamiento": forms.Textarea(attrs={"rows": 3}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, usuario=None, con_cita=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
        if not self.is_bound and not self.instance.pk:
            self.initial["fecha"] = timezone.localtime().strftime("%Y-%m-%dT%H:%M")
        if con_cita or self.instance.pk:
            del self.fields["mascota"]
        else:
            self.fields["mascota"].queryset = mascotas_visibles(usuario).filter(activa=True)
            self.fields["mascota"].required = True

    def clean_fecha(self):
        fecha = self.cleaned_data["fecha"]
        if fecha > timezone.now() + timedelta(minutes=5):
            raise ValidationError("La fecha de la atención no puede ser futura.")
        return fecha

    def datos_atencion(self):
        """Campos propios de la atención (sin la mascota, que solo sirve para elegir la ficha)."""
        return {c: v for c, v in self.cleaned_data.items() if c != "mascota"}


class RecetaForm(EstiloBootstrapMixin, forms.ModelForm):
    class Meta:
        model = Receta
        fields = ["medicamento", "dosis", "frecuencia", "duracion", "indicaciones"]
        widgets = {"indicaciones": forms.Textarea(attrs={"rows": 2})}


class ExamenForm(EstiloBootstrapMixin, forms.ModelForm):
    class Meta:
        model = Examen
        fields = ["tipo", "fecha", "resultado", "archivo"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "resultado": forms.Textarea(attrs={"rows": 2}),
            "archivo": forms.FileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # La fecha tiene valor por defecto (hoy). Sin esto Django exige un campo oculto
        # extra para saber si la fila "cambió"; así una fila que solo trae la fecha se ignora.
        self.fields["fecha"].show_hidden_initial = False


# Los formsets solo AGREGAN: lo ya escrito en una atención no se borra (registro clínico).
RecetaFormSet = modelformset_factory(Receta, form=RecetaForm, extra=2, can_delete=False)
ExamenFormSet = modelformset_factory(Examen, form=ExamenForm, extra=2, can_delete=False)


def datos_de_formset(formset):
    """Lista de dicts con las filas que la persona realmente llenó."""
    return [
        {k: v for k, v in form.cleaned_data.items() if k != "id"}
        for form in formset.forms
        if form.has_changed() and form.cleaned_data
    ]
