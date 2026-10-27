# ============================================================
# AGENDA/FORMS.PY / FORMULARIOS DE CITAS, DISPONIBILIDAD Y BLOQUEOS
# ============================================================
from datetime import date, datetime

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from clientes.servicios import mascotas_visibles
from core.forms import FormularioBase, FormularioModeloBase, volcar_errores

from . import servicios
from .models import BloqueoAgenda, DisponibilidadSemanal, Profesional


class CitaForm(FormularioBase):
    """
    Alta (y reprogramación) de una cita. La hora se elige entre los bloques
    LIBRES del profesional ese día; el selector se llena por fetch al cambiar
    profesional o fecha, y también en el servidor al volver a mostrar el formulario.
    """

    mascota = forms.ModelChoiceField(queryset=None, label="Mascota")
    profesional = forms.ModelChoiceField(queryset=Profesional.objects.none(), label="Veterinario")
    fecha = forms.DateField(label="Fecha", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    hora = forms.TimeField(label="Hora", widget=forms.Select(choices=[]), input_formats=["%H:%M", "%H:%M:%S"])
    motivo = forms.CharField(label="Motivo de la consulta", max_length=200)

    def __init__(self, *args, usuario, cita=None, **kwargs):
        self.usuario = usuario
        self.cita = cita
        super().__init__(*args, **kwargs)
        self.fields["mascota"].queryset = mascotas_visibles(usuario).filter(activa=True)
        self.fields["profesional"].queryset = Profesional.objects.select_related("usuario").filter(
            activo=True, usuario__is_active=True
        )
        if cita is not None:
            self.fields["mascota"].disabled = True
        self._cargar_horas()

    def _valor(self, nombre):
        if self.is_bound:
            return self.data.get(self.add_prefix(nombre))
        return self.initial.get(nombre)

    def _cargar_horas(self):
        """Rellena el <select> de horas con los bloques libres (si ya hay profesional y fecha)."""
        opciones = [("", "Elige un horario…")]
        try:
            profesional = Profesional.objects.get(pk=self._valor("profesional"))
            fecha = self._valor("fecha")
            fecha = fecha if isinstance(fecha, date) else date.fromisoformat(str(fecha))
            for h in servicios.horarios_libres(profesional, fecha, excluir_cita=self.cita):
                hora = timezone.localtime(h.inicio).strftime("%H:%M")
                opciones.append((hora, f"{hora} – {timezone.localtime(h.fin):%H:%M}"))
        except (Profesional.DoesNotExist, ValueError, TypeError):
            pass
        self.fields["hora"].widget.choices = opciones

    def inicio(self):
        d = self.cleaned_data
        return timezone.make_aware(datetime.combine(d["fecha"], d["hora"]))

    def guardar(self):
        """Devuelve la Cita o None (con el motivo del rechazo ya mostrado en el formulario)."""
        d = self.cleaned_data
        try:
            if self.cita is not None:
                return servicios.reprogramar_cita(
                    self.cita, usuario=self.usuario, inicio=self.inicio(), profesional=d["profesional"], motivo=d["motivo"]
                )
            return servicios.crear_cita(
                mascota=d["mascota"], profesional=d["profesional"], inicio=self.inicio(),
                motivo=d["motivo"], creada_por=self.usuario,
            )
        except ValidationError as error:
            volcar_errores(self, error)
            return None


class DisponibilidadForm(FormularioModeloBase):
    class Meta:
        model = DisponibilidadSemanal
        fields = ["profesional", "dia_semana", "hora_inicio", "hora_fin", "duracion_bloque_min"]
        widgets = {
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "hora_fin": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def __init__(self, *args, profesional=None, **kwargs):
        super().__init__(*args, **kwargs)
        if profesional is not None:
            # El veterinario solo define SU disponibilidad: el campo no se muestra.
            del self.fields["profesional"]
            self.instance.profesional = profesional


class BloqueoForm(FormularioModeloBase):
    class Meta:
        model = BloqueoAgenda
        fields = ["profesional", "inicio", "fin", "motivo"]
        widgets = {
            "inicio": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "fin": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, profesional=None, **kwargs):
        super().__init__(*args, **kwargs)
        if profesional is not None:
            del self.fields["profesional"]
            self.instance.profesional = profesional
