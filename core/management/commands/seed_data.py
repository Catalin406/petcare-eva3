# ============================================================
# COMANDO seed_data / DATOS DE DEMOSTRACIÓN (IDEMPOTENTE)
#   python manage.py seed_data [--con-correos]
# Crea usuarios de cada rol, veterinarios con disponibilidad, 3 tutores
# con 2 mascotas, citas pasadas atendidas (con ficha, recetas y exámenes),
# citas futuras, vacunas con próximas dosis variadas y los recordatorios.
# Se puede ejecutar varias veces: cada pieza se busca antes de crearse.
# Las contraseñas de demostración se restablecen en cada ejecución.
# ============================================================
from datetime import time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from agenda import servicios as servicios_agenda
from agenda.models import Cita, DisponibilidadSemanal, EstadoCita, HistorialCita, Profesional
from clientes import servicios as servicios_clientes
from clientes.models import Mascota, Tutor
from clinica import servicios as servicios_clinica
from clinica.models import Atencion
from core.fabricas import momento
from core.validadores import calcular_dv
from usuarios.models import Rol, Usuario
from vacunacion import servicios as servicios_vacunacion
from vacunacion.models import ControlPeriodico, RegistroVacuna, Vacuna

# ------------------------------------------------------------
# CREDENCIALES DE DEMOSTRACIÓN (solo para el entorno de evaluación)
# ------------------------------------------------------------
CLAVE_ADMIN = "Admin#2026Pet"
CLAVE_RECEPCION = "Recep#2026Pet"
CLAVE_VETERINARIO = "Vet#2026Pet"
CLAVE_TUTOR = "Tutor#2026Pet"

USUARIOS_INTERNOS = [
    # username, rol, nombre, apellido, clave
    ("admin", Rol.ADMINISTRADOR, "Administrador", "PetCare", CLAVE_ADMIN),
    ("recepcion", Rol.RECEPCIONISTA, "Valentina", "Cortés", CLAVE_RECEPCION),
]

VETERINARIOS = [
    # username, nombre, apellido, especialidad, bloques (día, desde, hasta)
    ("dra.munoz", "María José", "Muñoz", "Medicina general", [
        *[(d, time(9, 0), time(13, 0)) for d in range(0, 5)],
        *[(d, time(14, 30), time(18, 0)) for d in range(0, 5)],
        (5, time(10, 0), time(13, 0)),
    ]),
    ("dr.fuentes", "Andrés", "Fuentes", "Cirugía y traumatología", [
        *[(d, time(10, 0), time(14, 0)) for d in range(0, 5)],
        *[(d, time(15, 0), time(19, 0)) for d in range(0, 5)],
    ]),
]

TUTORES = [
    # username, nombre, apellido, cuerpo del RUT, teléfono, dirección, mascotas
    ("carolina.rojas", "Carolina", "Rojas", "15234567", "+56 9 8765 4321", "Av. Providencia 1234, Providencia", [
        ("Luna", "PERRO", "Labrador", "HEMBRA", 1500, "Dorada", "985112003004001"),
        ("Michi", "GATO", "Siamés", "MACHO", 900, "Crema con puntas oscuras", None),
    ]),
    ("felipe.araya", "Felipe", "Araya", "17456789", "+56 9 7654 3210", "Los Leones 456, Ñuñoa", [
        ("Rocky", "PERRO", "Pastor alemán", "MACHO", 2600, "Negro y fuego", "985112003004002"),
        ("Canela", "GATO", "Mestiza", "HEMBRA", 1100, "Atigrada café", None),
    ]),
    ("daniela.soto", "Daniela", "Soto", "19876543", "+56 9 6543 2109", "Manuel Montt 789, Providencia", [
        ("Toby", "PERRO", "Poodle", "MACHO", 1900, "Blanco", None),
        ("Piolín", "AVE", "Canario", "MACHO", 450, "Amarillo", None),
    ]),
]

VACUNAS = [
    # nombre, especie (vacío = todas), periodicidad en días
    ("Antirrábica", "", 365),
    ("Séxtuple canina", "PERRO", 365),
    ("Tos de las perreras", "PERRO", 180),
    ("Triple felina", "GATO", 365),
    ("Leucemia felina", "GATO", 365),
]

# (mascota, vacuna, días hasta la próxima dosis: negativo = vencida)
PLAN_VACUNAS = [
    ("Luna", "Antirrábica", -20),           # vencida
    ("Michi", "Triple felina", 5),          # dentro de 7 días
    ("Rocky", "Séxtuple canina", 25),       # dentro de 30 días
    ("Rocky", "Antirrábica", 200),          # vigente
    ("Canela", "Triple felina", -3),        # vencida
    ("Toby", "Tos de las perreras", 7),     # justo en 7 días
    ("Luna", "Séxtuple canina", 18),        # dentro de 30 días
    ("Canela", "Leucemia felina", 60),      # fuera de la ventana de 30 días
]

CONTROLES = [
    ("Luna", "Control de peso y dieta", 10),
    ("Rocky", "Control de displasia de cadera", -5),
    ("Toby", "Control dental", 21),
]

# Atenciones históricas: (mascota, veterinario, días atrás, hora, motivo, anamnesis, diagnóstico, tratamiento, peso, temperatura, receta, examen)
ATENCIONES = [
    ("Luna", "dra.munoz", 40, "10:00", "Control anual", "Control de rutina; sin molestias. Come y bebe normal.",
     "Paciente sana. Leve sarro grado I.", "Dieta balanceada y cepillado dental semanal.", "29.40", "38.4",
     ("Antiparasitario externo", "1 comprimido", "Cada 3 meses", "Permanente", "Con comida."), ("Hemograma completo", "Valores dentro de rangos normales.")),
    ("Rocky", "dr.fuentes", 30, "11:00", "Cojera pata trasera", "Cojea desde hace 4 días tras jugar en el parque.",
     "Esguince leve de rodilla derecha.", "Reposo relativo 10 días y antiinflamatorio.", "34.80", "38.7",
     ("Meloxicam", "0,1 mg/kg", "Cada 24 horas", "7 días", "Administrar con comida."), ("Radiografía de rodilla", "Sin fracturas; leve aumento de volumen articular.")),
    ("Michi", "dra.munoz", 25, "12:00", "Vómitos ocasionales", "Vomita pelo 2 veces por semana.",
     "Tricobezoares leves.", "Malta en pasta y cepillado diario.", "4.10", "38.6",
     ("Pasta de malta", "2 cm", "Cada 48 horas", "15 días", "Directo o sobre las patas."), None),
    ("Canela", "dra.munoz", 18, "10:30", "Vacunación y control", "Control para vacuna anual; sin síntomas.",
     "Paciente sana; vacuna aplicada.", "Control en un año.", "3.70", "38.5", None, None),
    ("Toby", "dr.fuentes", 12, "12:30", "Picazón en oídos", "Se rasca las orejas y sacude la cabeza.",
     "Otitis externa bilateral.", "Limpieza ótica y gotas por 10 días.", "6.20", "38.9",
     ("Gotas óticas (ciprofloxacino)", "5 gotas por oído", "Cada 12 horas", "10 días", "Limpiar antes de aplicar."), ("Citología ótica", "Presencia de levaduras (Malassezia).")),
    ("Piolín", "dra.munoz", 6, "11:30", "Plumas opacas", "Plumaje opaco y menos canto.",
     "Déficit vitamínico leve.", "Suplemento vitamínico y más luz natural.", "0.45", "40.5",
     ("Complejo vitamínico", "2 gotas en el agua", "Diario", "20 días", "Renovar el agua cada día."), None),
]

# Citas futuras: (mascota, veterinario, días desde hoy, hora, motivo, confirmar)
CITAS_FUTURAS = [
    ("Luna", "dra.munoz", 3, "10:00", "Control de peso y dieta", True),
    ("Michi", "dra.munoz", 4, "11:00", "Vacuna triple felina", False),
    ("Rocky", "dr.fuentes", 5, "10:30", "Revisión de rodilla", True),
    ("Canela", "dra.munoz", 6, "15:00", "Control post vacuna", False),
    ("Toby", "dr.fuentes", 8, "16:00", "Revisión de oídos", False),
    ("Piolín", "dra.munoz", 9, "09:30", "Control de plumaje", False),
]

# PDF mínimo válido para los exámenes de demostración
PDF_DEMO = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 100]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
)


def _dia_habil(fecha, hacia):
    """Si cae en fin de semana, avanza (+1) o retrocede (-1) al día hábil más cercano."""
    while fecha.weekday() > 4:
        fecha += timedelta(days=hacia)
    return fecha


class Command(BaseCommand):
    help = "Carga datos de demostración (idempotente) e imprime las credenciales."

    def add_arguments(self, parser):
        parser.add_argument("--con-correos", action="store_true", help="También envía los correos de recordatorio (a la consola por defecto).")

    @transaction.atomic
    def handle(self, *args, **opciones):
        self.hoy = timezone.localdate()
        self._usuarios_internos()
        self.profesionales = self._veterinarios()
        self.vacunas = self._vacunas()
        self.mascotas = self._tutores_y_mascotas()
        self._atenciones_pasadas()
        self._citas_futuras()
        self._vacunas_aplicadas()
        self._controles()
        resumen = servicios_vacunacion.generar_recordatorios(enviar=opciones["con_correos"])
        self.stdout.write(self.style.SUCCESS(
            f"Recordatorios: {resumen['creados']} creados, {resumen['vencidos']} vencidos, {resumen['enviados']} correos."
        ))
        self._imprimir_credenciales()

    # ---------------- usuarios y profesionales ----------------
    def _usuario(self, username, rol, nombre, apellido, clave, email=None):
        usuario, _ = Usuario.objects.get_or_create(username=username, defaults={"rol": rol})
        usuario.rol, usuario.first_name, usuario.last_name = rol, nombre, apellido
        usuario.email = email or f"{username}@petcare.example.com"
        usuario.is_active = True
        usuario.set_password(clave)  # se restablece siempre: las credenciales impresas siempre sirven
        usuario.save()
        return usuario

    def _usuarios_internos(self):
        for username, rol, nombre, apellido, clave in USUARIOS_INTERNOS:
            self._usuario(username, rol, nombre, apellido, clave)

    def _veterinarios(self):
        profesionales = {}
        for username, nombre, apellido, especialidad, bloques in VETERINARIOS:
            usuario = self._usuario(username, Rol.VETERINARIO, nombre, apellido, CLAVE_VETERINARIO)
            prof, _ = Profesional.objects.update_or_create(usuario=usuario, defaults={"especialidad": especialidad, "activo": True})
            for dia, desde, hasta in bloques:
                DisponibilidadSemanal.objects.update_or_create(
                    profesional=prof, dia_semana=dia, hora_inicio=desde,
                    defaults={"hora_fin": hasta, "duracion_bloque_min": 30},
                )
            profesionales[username] = prof
        return profesionales

    def _vacunas(self):
        vacunas = {}
        for nombre, especie, dias in VACUNAS:
            vacunas[nombre], _ = Vacuna.objects.update_or_create(
                nombre=nombre, defaults={"especie_aplicable": especie, "periodicidad_dias": dias, "activa": True}
            )
        return vacunas

    # ---------------- tutores y mascotas ----------------
    def _tutores_y_mascotas(self):
        mascotas = {}
        for username, nombre, apellido, cuerpo, telefono, direccion, lista in TUTORES:
            rut = f"{cuerpo}-{calcular_dv(cuerpo)}"
            tutor = Tutor.objects.filter(rut=rut).select_related("usuario").first()
            if tutor is None:
                tutor = servicios_clientes.crear_tutor(
                    username=username, password=CLAVE_TUTOR, first_name=nombre, last_name=apellido,
                    email=f"{username}@example.com", rut=rut, telefono=telefono, direccion=direccion,
                )
            else:
                tutor.usuario.set_password(CLAVE_TUTOR)
                tutor.usuario.is_active = True
                tutor.usuario.save()
            for nombre_m, especie, raza, sexo, peso_g, senas, chip in lista:
                mascota, _ = Mascota.objects.get_or_create(
                    tutor=tutor, nombre=nombre_m,
                    defaults={
                        "especie": especie, "raza": raza, "sexo": sexo, "peso": Decimal(peso_g) / 1000,
                        "color_senas": senas, "microchip": chip, "activa": True,
                        "fecha_nacimiento": self.hoy - timedelta(days=365 * (1 + len(mascotas) % 5) + 45 * len(mascotas)),
                    },
                )
                mascotas[nombre_m] = mascota
        return mascotas

    # ---------------- historial clínico ----------------
    def _atenciones_pasadas(self):
        for nombre, vet, dias_atras, hora, motivo, anamnesis, diagnostico, tratamiento, peso, temp, receta, examen in ATENCIONES:
            mascota, prof = self.mascotas[nombre], self.profesionales[vet]
            if Atencion.objects.filter(ficha__mascota=mascota, veterinario=prof, cita__motivo=motivo).exists():
                continue
            fecha = _dia_habil(self.hoy - timedelta(days=dias_atras), -1)
            inicio = momento(fecha, hora)
            cita = Cita.objects.create(
                mascota=mascota, profesional=prof, inicio=inicio, fin=inicio + timedelta(minutes=30), motivo=motivo,
                estado=EstadoCita.CONFIRMADA, creada_por=Usuario.objects.get(username="recepcion"),
            )
            HistorialCita.objects.bulk_create([
                HistorialCita(cita=cita, estado_anterior="", estado_nuevo=EstadoCita.PROGRAMADA, comentario="Cita creada"),
                HistorialCita(cita=cita, estado_anterior=EstadoCita.PROGRAMADA, estado_nuevo=EstadoCita.CONFIRMADA, comentario="Confirmada por teléfono"),
            ])
            recetas = []
            if receta:
                medicamento, dosis, frecuencia, duracion, indicaciones = receta
                recetas.append({"medicamento": medicamento, "dosis": dosis, "frecuencia": frecuencia, "duracion": duracion, "indicaciones": indicaciones})
            examenes = []
            if examen:
                tipo, resultado = examen
                examenes.append({
                    "tipo": tipo, "fecha": fecha, "resultado": resultado,
                    "archivo": ContentFile(PDF_DEMO, name=f"{tipo.lower().replace(' ', '_')}_{mascota.nombre.lower()}.pdf"),
                })
            servicios_clinica.registrar_atencion(
                veterinario=prof, ficha=mascota.ficha, cita=cita, recetas=recetas, examenes=examenes,
                datos={
                    "fecha": inicio + timedelta(minutes=5), "anamnesis": anamnesis, "diagnostico": diagnostico,
                    "tratamiento": tratamiento, "peso_kg": peso, "temperatura_c": temp,
                    "observaciones": "Se explican los cuidados al tutor.",
                },
            )
        # Ficha general con datos clínicos de ejemplo
        ficha = self.mascotas["Luna"].ficha
        if not ficha.alergias:
            ficha.alergias, ficha.antecedentes = "Alergia a la penicilina.", "Esterilizada a los 2 años. Sin cirugías posteriores."
            ficha.save()

    def _citas_futuras(self):
        recepcion = Usuario.objects.get(username="recepcion")
        for nombre, vet, dias, hora, motivo, confirmar in CITAS_FUTURAS:
            mascota, prof = self.mascotas[nombre], self.profesionales[vet]
            if Cita.objects.filter(mascota=mascota, inicio__gt=timezone.now()).exclude(estado=EstadoCita.CANCELADA).exists():
                continue  # ya tiene una cita futura: no se acumulan más con cada ejecución
            fecha = _dia_habil(self.hoy + timedelta(days=dias), 1)
            try:
                cita = servicios_agenda.crear_cita(
                    mascota=mascota, profesional=prof, inicio=momento(fecha, hora), motivo=motivo, creada_por=recepcion
                )
                if confirmar:
                    servicios_agenda.cambiar_estado(cita, EstadoCita.CONFIRMADA, usuario=recepcion, comentario="Confirmada por teléfono")
            except ValidationError as error:
                self.stdout.write(self.style.WARNING(f"  Cita de {nombre} omitida: {' '.join(error.messages)}"))

    def _vacunas_aplicadas(self):
        veterinaria = self.profesionales["dra.munoz"]
        for nombre, vacuna, dias_hasta_proxima in PLAN_VACUNAS:
            mascota, v = self.mascotas[nombre], self.vacunas[vacuna]
            if RegistroVacuna.objects.filter(mascota=mascota, vacuna=v).exists():
                continue
            RegistroVacuna.objects.create(
                mascota=mascota, vacuna=v, veterinario=veterinaria, lote=f"L{1000 + len(nombre) * 37 + len(vacuna) * 11}",
                fecha_aplicacion=self.hoy + timedelta(days=dias_hasta_proxima) - timedelta(days=v.periodicidad_dias),
            )

    def _controles(self):
        for nombre, motivo, dias in CONTROLES:
            ControlPeriodico.objects.get_or_create(
                mascota=self.mascotas[nombre], motivo=motivo, defaults={"fecha_programada": self.hoy + timedelta(days=dias)}
            )

    # ---------------- salida ----------------
    def _imprimir_credenciales(self):
        filas = [
            ("Administrador", "admin", CLAVE_ADMIN),
            ("Recepcionista", "recepcion", CLAVE_RECEPCION),
            ("Veterinaria", "dra.munoz", CLAVE_VETERINARIO),
            ("Veterinario", "dr.fuentes", CLAVE_VETERINARIO),
            *[("Tutor/a", t[0], CLAVE_TUTOR) for t in TUTORES],
        ]
        self.stdout.write("\n" + self.style.MIGRATE_HEADING("CREDENCIALES DE DEMOSTRACIÓN"))
        self.stdout.write(f"  {'Rol':<15}{'Usuario':<18}Contraseña")
        self.stdout.write("  " + "-" * 48)
        for rol, usuario, clave in filas:
            self.stdout.write(f"  {rol:<15}{usuario:<18}{clave}")
        self.stdout.write("")
