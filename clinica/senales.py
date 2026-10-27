# ============================================================
# CLINICA/SENALES.PY / FICHA AUTOMÁTICA AL CREAR LA MASCOTA
# Va en una señal (y no en la vista) para que funcione igual desde la
# web, la API, el Django Admin y el seed: ninguna mascota queda sin ficha.
# ============================================================
from django.db.models.signals import post_save
from django.dispatch import receiver

from clientes.models import Mascota

from .models import FichaClinica


@receiver(post_save, sender=Mascota)
def crear_ficha_de_la_mascota(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        FichaClinica.objects.get_or_create(mascota=instance)
