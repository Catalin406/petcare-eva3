# ============================================================
# COMANDO generar_recordatorios
# Pensado para correr una vez al día (cron). Es idempotente:
#   python manage.py generar_recordatorios [--dias 30] [--sin-correo]
# ============================================================
from django.conf import settings
from django.core.management.base import BaseCommand

from vacunacion import servicios


class Command(BaseCommand):
    help = "Crea recordatorios de vacunas y controles próximos, marca los vencidos y avisa por correo a los tutores."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias", type=int, default=None,
            help=f"Días hacia adelante a revisar (por defecto {settings.DIAS_ANTICIPACION_RECORDATORIO}, configurable en .env).",
        )
        parser.add_argument("--sin-correo", action="store_true", help="No envía correos, solo actualiza los recordatorios.")

    def handle(self, *args, **opciones):
        r = servicios.generar_recordatorios(dias=opciones["dias"], enviar=not opciones["sin_correo"])
        self.stdout.write(self.style.SUCCESS(
            f"Recordatorios: {r['creados']} creados, {r['vencidos']} marcados vencidos, "
            f"{r['completados']} completados, {r['enviados']} correos enviados."
        ))
        if r["sin_correo"]:
            self.stdout.write(f"  {r['sin_correo']} sin correo del tutor (quedan solo en el sistema).")
        if r["errores_envio"]:
            self.stdout.write(self.style.WARNING(f"  {r['errores_envio']} correos fallaron y se reintentarán en la próxima ejecución."))
