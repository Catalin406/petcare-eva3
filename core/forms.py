# ============================================================
# CORE/FORMS.PY / ESTILO COMÚN DE FORMULARIOS
# Aplica las clases de Bootstrap a todos los widgets y marca con
# is-invalid los campos con error, para que los mensajes se vean
# junto al campo (plantilla parciales/campo_form.html).
# ============================================================
from django import forms


class EstiloBootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, (forms.CheckboxInput,)):
                clase = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                clase = "form-select"
            elif isinstance(widget, forms.ClearableFileInput):
                clase = "form-control"
            else:
                clase = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {clase}".strip()

    def is_valid(self):
        valido = super().is_valid()
        # Se marca después de validar, cuando ya se conocen los errores.
        for nombre in self.errors:
            if nombre in self.fields:
                w = self.fields[nombre].widget
                w.attrs["class"] = f"{w.attrs.get('class', '')} is-invalid".strip()
        return valido


class FormularioBase(EstiloBootstrapMixin, forms.Form):
    pass


class FormularioModeloBase(EstiloBootstrapMixin, forms.ModelForm):
    pass
