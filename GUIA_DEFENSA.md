# Guía de defensa — PetCare

Documento de estudio para la defensa oral de la Evaluación 3. Está escrito en lenguaje simple: la idea es que puedas **explicar con tus palabras** y **mostrar en vivo** cada cosa.

> Regla de oro de la defensa: cuando afirmes algo, **muéstralo** (una ruta, un archivo, una prueba). Aquí tienes dónde.

---

## 1. La arquitectura en 2 minutos

```
Navegador ──https──▶ Nginx ──http──▶ Gunicorn ──▶ Django ──▶ PostgreSQL
 (usuario)  :443     (portero)  127.0.0.1:8000  (la app)    (la base de datos)
```

| Pieza | Qué hace (en simple) | Dónde se ve en el proyecto |
|---|---|---|
| **Navegador** | Pide páginas y manda formularios. Guarda la cookie de sesión. | — |
| **Nginx** | Es el "portero": recibe el tráfico de Internet, maneja el **HTTPS** (certificado Let's Encrypt), entrega los archivos estáticos y reenvía el resto a Gunicorn. **No** sirve los archivos clínicos. | `deploy/nginx-petcare.conf` |
| **Gunicorn** | Ejecuta Django de forma estable (3 procesos) y se reinicia solo (systemd). Solo escucha en `127.0.0.1`, así que desde Internet no se llega directo. | `deploy/gunicorn-petcare.service` |
| **Django** | La aplicación: rutas (`urls.py`), vistas, reglas de negocio (`servicios.py`), plantillas, API y Admin. | `config/`, `agenda/`, `clinica/`… |
| **PostgreSQL** | Guarda los datos y **hace cumplir reglas** (únicos, checks, exclusión de horarios). | `*/migrations/`, `*/models.py` |

**Qué pasa cuando alguien abre una página** (ejemplo: `https://codelab-catalina.duckdns.org/mascotas/`):

1. El navegador abre una conexión HTTPS con Nginx (puerto 443).
2. Nginx descifra, agrega las cabeceras (`include proxy_params`: entre ellas `X-Forwarded-Proto: https`) y se la pasa a Gunicorn.
3. Gunicorn llama a Django. Los *middlewares* corren en orden: seguridad, sesión, CSRF, autenticación y **`LoginRequeridoMiddleware`** (si no hay sesión → redirige al login).
4. Django elige la vista según la URL. La vista (`MascotaListaView`) revisa el **rol** (`RolRequeridoMixin`) y pide los datos a través del *queryset filtrado por usuario* (`mascotas_visibles`).
5. El ORM traduce eso a SQL y PostgreSQL responde.
6. Django renderiza la plantilla y la respuesta vuelve por el mismo camino.

**Por qué esta separación:** Nginx es muy bueno con conexiones y archivos; Gunicorn es un servidor de aplicaciones Python; Django se concentra en la lógica; PostgreSQL protege la integridad de los datos. Cada uno hace una cosa bien.

### Capas del código (para explicar el "orden")

```
Vista / API (views.py, api.py)  →  solo orquesta: permisos, formularios, mensajes
        │ llama a
Servicios (servicios.py)        →  TODA la lógica de negocio (una sola fuente de verdad)
        │ usa
Modelos + Constraints           →  datos y reglas que la base de datos hace cumplir
```

La web, la API, el Django Admin y el `seed_data` usan **los mismos servicios**: por eso las reglas no se pueden "saltar" entrando por otra puerta.

---

## 2. Cómo se cumple cada criterio de la rúbrica

### Criterio 1 — PostgreSQL

| Qué piden | Dónde está / cómo mostrarlo |
|---|---|
| Conexión por variables de entorno | `config/settings.py` → `DATABASES` con `config("DB_NAME")`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`. Plantilla: `.env.example`. |
| Migraciones limpias | `python manage.py makemigrations --check` → "No changes detected". Carpetas `*/migrations/0001_initial.py`. |
| ForeignKey / OneToOne con `on_delete` pensado | `Tutor.usuario` OneToOne `PROTECT` · `Mascota.tutor` FK `PROTECT` · `FichaClinica.mascota` OneToOne `CASCADE` (solo cae si la mascota se borra, y eso solo se permite sin historial) · `Atencion.ficha` FK `PROTECT` · `Cita.creada_por` FK `SET_NULL` · `HistorialCita.cita` FK `CASCADE`. |
| `UniqueConstraint` | `Mascota`: `mascota_microchip_unico` (condicional) y `mascota_nombre_unico_por_tutor` (por tutor, sin distinguir mayúsculas) · `Usuario`: `usuario_email_unico_ci` · `Recordatorio`: únicos por origen y fecha · `RegistroVacuna` único por día. `Tutor.rut` es `unique`. |
| `CheckConstraint` | `Tutor`: formato de RUT · `Mascota`: peso > 0, microchip 15 dígitos · `Cita`: fin > inicio · `DisponibilidadSemanal`: fin > inicio, duración 5–240 min · `Atencion`: temperatura 30–45 °C · `Vacuna`: periodicidad > 0 · `Recordatorio`: origen coherente con el tipo. |
| **`ExclusionConstraint`** | `agenda/models.py` → `Cita`: `cita_sin_solape_profesional` y `cita_sin_solape_mascota`, con `TSTZRANGE(inicio, fin)` y condición `~Q(estado="CANCELADA")`. La extensión se crea en `agenda/migrations/0001_initial.py` (`BtreeGistExtension()`); `django.contrib.postgres` está en `INSTALLED_APPS`. |

### Criterio 2 — Django Admin

| Qué piden | Dónde está |
|---|---|
| **Todos** los modelos registrados | `*/admin.py`. La prueba `core/test_admin.py::test_todos_los_modelos_del_dominio_estan_registrados` lo comprueba. |
| `list_display`, `list_filter`, `search_fields`, `date_hierarchy` | En cada `ModelAdmin` (p. ej. `CitaAdmin`: fecha/mascota/profesional/estado; filtros por estado y profesional; búsqueda por mascota o RUT; jerarquía por fecha). |
| Inlines | `TutorAdmin` → mascotas (`MascotaInline`) · `AtencionAdmin` → recetas y exámenes · `CitaAdmin` → historial · `ProfesionalAdmin` → disponibilidad y bloqueos. |
| `readonly_fields` de auditoría | `creada_en`, `actualizada_en`, `creada_por`, `proxima_dosis`, `is_staff`… |
| Acciones masivas | Confirmar / cancelar / "No asistió" citas (pasan por `cambiar_estado`, respetan transiciones) · activar/desactivar mascotas, cuentas y vacunas · completar recordatorios · marcar controles realizados · ejecutar la generación de recordatorios. |
| Insignias de color con `format_html` | `core/admin.py::insignia()` y los estilos `.pc-insignia` en `static/admin/css/petcare_admin.css`. |
| Plantillas propias + marca | `templates/admin/base_site.html` (cabecera PetCare con ícono), `templates/admin/index.html` (bienvenida) y el CSS con la paleta rosado/café. |
| Textos en español | `core/admin.py`: `site_header`, `site_title`, `index_title`. |

### Criterio 3 — CRUD y reglas de negocio

| Funcionalidad | Web | API | Reglas (archivo) |
|---|---|---|---|
| 1. Tutores y mascotas | `/tutores/`, `/mascotas/` | `/api/tutores/`, `/api/mascotas/` | `clientes/servicios.py` (RUT, desactivar vs eliminar), `core/validadores.py` (dígito verificador) |
| 2. Agenda | `/agenda/calendario/`, `/agenda/citas/`, `/agenda/disponibilidad/` | `/api/citas/`, `/api/profesionales/{id}/horarios/`, `/api/agenda/eventos/` | `agenda/servicios.py` (`crear_cita`, `cambiar_estado`, `horarios_libres`, `TRANSICIONES`) |
| 3. Ficha clínica | `/clinica/fichas/<id>/`, `/clinica/atenciones/nueva/` | `/api/fichas/`, `/api/atenciones/`, `/api/examenes/` | `clinica/servicios.py` (`registrar_atencion` atómico) |
| 4. Vacunas y recordatorios | `/recordatorios/`, `/vacunacion/…` | `/api/recordatorios/`, `/api/registros-vacuna/` | `vacunacion/servicios.py`, comando `generar_recordatorios` |

### Criterio 4 — Seguridad, sesiones e IA

| Qué piden | Dónde está / cómo mostrarlo |
|---|---|
| `LoginView` / `LogoutView`, logout por POST | `usuarios/views.py`, `usuarios/urls.py`. Un `GET /logout/` responde **405**; el botón "Salir" es un formulario POST con token CSRF. |
| Sesión con expiración configurable | `SESSION_EXPIRA_SEGUNDOS` (30 min por defecto) + `SESSION_SAVE_EVERY_REQUEST` (se renueva con la actividad). |
| **Toda** la web exige login | `core/middleware.py::LoginRequeridoMiddleware` + `RolRequeridoMixin` en cada vista. Prueba: `core/tests.py::test_todas_las_rutas_web_exigen_login`. |
| Permisos por rol (web y API/JWT) | `core/mixins.py` y `core/permisos_api.py::PorRol`; matriz rol × ruta en `core/test_matriz_roles.py`. |
| Objeto: un tutor no ve datos de otro | Los *querysets* parten de `mascotas_visibles()`, `citas_visibles()`, `fichas_visibles()`… → lo ajeno responde **404**. Pruebas en `clientes/tests.py`, `agenda/tests.py`, `clinica/tests.py`, `vacunacion/tests.py`. |
| Validadores de contraseña | `AUTH_PASSWORD_VALIDATORS` (mínimo 10 caracteres, no común, no numérica, no parecida al usuario). |
| Cookies seguras por `.env` | `DETRAS_DE_PROXY_HTTPS` / `COOKIES_SEGURAS` → `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, HSTS, redirección a https. |
| CSRF intacto | `CsrfViewMiddleware` activo; pruebas en `core/test_seguridad.py` (POST sin token → 403). |
| Archivos privados | `core/archivos.py` (almacenamiento sin URL pública) + vistas `mascota_foto` y `examen_archivo`. |
| `prompts_ia.md` | En la raíz del repositorio. |

### Criterio 5 — Despliegue y defensa

`README.md` (ejecución local y despliegue, IP `54.152.231.63`, URL `https://codelab-catalina.duckdns.org`, credenciales de demostración), carpeta `deploy/` y este documento.

---

## 3. Guion de demostración en vivo (≈ 12 minutos)

Ten abiertas **dos ventanas** (una normal y una privada) para cambiar de usuario sin cerrar sesión. Antes de empezar: `python manage.py seed_data` (restablece las claves de demostración).

### A. Recepción: el problema de las citas solapadas (3 min)
1. Entra como **`recepcion`**. Muestra el **inicio** (resumen del día) y la **navbar** (ve Tutores, Mascotas, Citas… pero **no** "Disponibilidad" ni "Administración").
2. **Tutores → Nuevo tutor**: escribe un RUT con dígito verificador malo (`12.345.678-9`) → mensaje claro. Corrige a `12.345.678-5` → se crea.
3. **Mascotas → Nueva mascota** para ese tutor. Di: *"Su ficha clínica se creó sola"* (es una señal, `clinica/senales.py`).
4. **Calendario**: elige a la Dra. Muñoz. Los bloques verdes son libres, los rojos ocupados. Esto lo pinta FullCalendar con un `fetch` a `/api/agenda/eventos/` (asíncrono).
5. Haz clic en un bloque **verde** → el formulario viene relleno → agenda la cita.
6. Intenta agendar **la misma hora** otra vez → *"Dra. … ya tiene una cita…"*. Explica las **dos capas**: el mensaje amable (servicio) y la `ExclusionConstraint` de PostgreSQL por si dos personas reservan a la vez.
7. Prueba una hora **fuera de horario** o **en el pasado** → rechazadas con mensaje.
8. En el detalle de la cita, **Confirmar** y mira el **historial** (quién y cuándo).
9. Intenta abrir `/clinica/fichas/1/` → **403** (recepción no ve datos clínicos).

### B. Veterinario: ficha clínica (3 min)
1. Entra como **`dra.munoz`** (ventana privada). Inicio = *"Tu agenda de hoy"*.
2. Abre una cita **confirmada** → **Registrar atención**. Completa diagnóstico, una receta y adjunta un PDF (prueba también uno `.exe` o de más de 5 MB → rechazado).
3. Al guardar: la cita pasa a **Atendida** *en la misma transacción* (muéstralo en el historial de la cita).
4. Abre la **ficha** de la mascota: línea de tiempo con atenciones y vacunas.
5. **Disponibilidad**: intenta crear una franja que se superponga con otra → *"se superpone"*.
6. Di: *"No existe botón ni ruta para borrar atenciones: es un registro clínico."*

### C. Tutor: privacidad (2 min)
1. Entra como **`carolina.rojas`**. Solo ve **sus** mascotas, citas y recordatorios.
2. En la barra de direcciones cambia el id de una mascota por el de otra persona → **404**.
3. Abre la ficha de su mascota (solo lectura) y el adjunto del examen (se descarga por una vista protegida).
4. Prueba `https://…/media/…` → 404: **los archivos no son públicos**.
5. **Recordatorios**: tres bloques con colores de urgencia (vencidos, 7 días, 30 días).
6. Cancela una cita propia (respetando la anticipación mínima).

### D. API y Swagger (2 min)
1. Con la sesión ya iniciada en el sitio, abre `/api/docs/` (sin sesión redirige al login). **Authorize** tras `POST /api/auth/token/` con `carolina.rojas`.
2. `GET /api/mascotas/` → solo las suyas. `GET /api/mascotas/{id de otra}` → **404**.
3. Entra con `recepcion`: `GET /api/atenciones/` → **403**.

### E. Django Admin (2 min)
1. Entra a `/admin/` como **`admin`** (los demás roles son redirigidos al login del Admin).
2. Muestra la **marca PetCare** (cabecera y colores), "Gestión de la clínica veterinaria".
3. **Citas**: insignias de colores, filtros, búsqueda, jerarquía por fecha y la **acción masiva** "Confirmar".
4. **Tutores**: dentro de un tutor, el *inline* de mascotas.
5. **Atenciones**: solo lectura, con recetas y exámenes en *inlines*; el adjunto abre la vista protegida.
6. **Usuarios**: `is_staff` aparece de solo lectura (lo calcula el rol).

### F. Terminal (1 min)
```
python manage.py generar_recordatorios     # crea / marca vencidos / "envía" correos (a consola)
python manage.py generar_recordatorios     # segunda vez: 0 creados, 0 correos → idempotente
python manage.py test                      # todas las pruebas en verde
```

---

## 4. Treinta preguntas probables (con respuesta)

**Arquitectura y despliegue**

1. **¿Por qué Nginx *y* Gunicorn?** Gunicorn ejecuta Python pero no está pensado para recibir Internet directo (HTTPS, conexiones lentas, estáticos). Nginx hace de portero y Gunicorn de motor de la app.
2. **¿Qué hace `include proxy_params`?** Agrega las cabeceras `Host`, `X-Real-IP`, `X-Forwarded-For` y `X-Forwarded-Proto`. Django necesita la última para saber que el usuario entró por https.
3. **¿Qué es `DETRAS_DE_PROXY_HTTPS`?** Una variable de `.env` que activa `SECURE_PROXY_SSL_HEADER`, la redirección a https, las cookies seguras y HSTS. En local está apagada para poder trabajar con http.
4. **¿Por qué `CSRF_TRUSTED_ORIGINS`?** Django compara el origen del POST con el host; detrás de un proxy con https hay que decirle explícitamente que `https://codelab-catalina.duckdns.org` es de confianza.
5. **¿Qué puertos abriste en el grupo de seguridad y por qué?** 22 (solo mi IP), 80 y 443. El 5432 (PostgreSQL) y el 8000 (Gunicorn) quedan cerrados: solo se usan dentro del servidor.
6. **¿Cómo se renueva el certificado?** Certbot instala un temporizador que renueva Let's Encrypt automáticamente (cada ~60 días).

**Base de datos**

7. **¿Por qué una `ExclusionConstraint` si ya validas en el servicio?** Porque la validación en Python puede fallar con **concurrencia** (dos peticiones validan a la vez y ambas pasan). La base de datos es la última barrera y es atómica.
8. **¿Qué es `btree_gist` y `tstzrange`?** `tstzrange` es un rango de fechas con zona horaria. `btree_gist` permite combinar en un mismo índice "rangos que se solapan" con "igualdad" (mismo profesional). Sin la extensión no se puede crear la restricción.
9. **¿Por qué las citas canceladas quedan fuera?** La restricción tiene `condition=~Q(estado="CANCELADA")`: cancelar libera el horario. `ATENDIDA` y `NO_ASISTIO` siguen ocupándolo porque ese horario ya se usó.
10. **¿Por qué no usaste `ExclusionConstraint` en la disponibilidad semanal?** PostgreSQL no tiene un tipo de rango de solo horas y no quise tipos propios que compliquen el despliegue. Ahí valido el solape en `servicios.py` y lo pruebo.
11. **¿Qué significa `on_delete=PROTECT`?** Impide borrar un registro si otro depende de él (p. ej. un veterinario con atenciones). Evita perder historial clínico por accidente. `CASCADE` borra en cadena; `SET_NULL` deja el campo vacío.
12. **¿Qué es una migración y por qué `makemigrations --check`?** Es el historial versionado del esquema de la base. `--check` falla si los modelos cambiaron sin migración: garantiza que el repositorio y la base no se desfasen.

**Reglas de negocio**

13. **¿Cómo evitas el solape entre dos usuarios reservando a la vez?** `crear_cita` corre en una transacción y bloquea con `select_for_update` a la mascota y al profesional; si aun así algo se cuela, salta la `ExclusionConstraint` y se traduce a *"Ese horario acaba de ser ocupado"*.
14. **¿Cómo funcionan las transiciones de estado?** Hay un diccionario `TRANSICIONES` en `agenda/servicios.py` con los destinos válidos de cada estado. `ATENDIDA`, `CANCELADA` y `NO_ASISTIO` son finales. Cada cambio queda en `HistorialCita`.
15. **¿Por qué una cita solo pasa a `ATENDIDA` al registrar la atención?** Para que nunca haya una cita "atendida" sin registro clínico. Se hace en una transacción: si la atención falla, la cita no cambia.
16. **¿Cómo se calcula la próxima dosis?** En `RegistroVacuna.save()`: fecha de aplicación + `periodicidad_dias` de la vacuna. No se puede editar a mano.
17. **¿Qué significa que `generar_recordatorios` sea idempotente?** Correrlo dos veces da el mismo resultado: no duplica avisos (`get_or_create` + restricciones únicas) ni reenvía correos (`enviado_en`).
18. **¿Cómo validas el RUT?** Normalizo (sin puntos, DV en mayúscula), compruebo el formato y calculo el dígito verificador con módulo 11 (`core/validadores.py`). Además hay un `CheckConstraint` con el formato en la base.
19. **¿Por qué una mascota con historial se "desactiva" y no se borra?** Por trazabilidad clínica y por `PROTECT`. `eliminar_o_desactivar_mascota` decide: sin historial la borra, con historial la desactiva.
20. **¿Por qué el correo del tutor vive solo en `Usuario`?** Una sola fuente de verdad: así no hay dos correos que se desincronicen. Los recordatorios usan `tutor.usuario.email`.

**Seguridad y permisos**

21. **¿Cómo sincronizas `is_staff` con el rol?** En `Usuario.save()`: `is_staff = (rol == ADMINISTRADOR)`. Aunque alguien intente forzarlo, se corrige al guardar (hay prueba).
22. **¿Cómo evitas que un tutor vea datos de otro?** Nunca busco un objeto "por id a secas": parto de un queryset filtrado por usuario (`mascotas_visibles`). Si el objeto es de otro, para el usuario *no existe* → 404 (en web y API).
23. **¿Por qué 404 y no 403 para lo ajeno?** El 403 confirma que el recurso existe; el 404 no filtra información.
24. **¿Qué es CSRF y cómo te protege Django?** Un ataque donde otro sitio hace que tu navegador envíe un POST con tu sesión. Django exige un token secreto en cada formulario POST (`{% csrf_token %}`) y rechaza con 403 si falta.
25. **¿Por qué el logout es por POST?** Un enlace GET podría cerrar la sesión de alguien desde otra página (ataque de "logout CSRF"). Django 5 solo acepta POST.
26. **Sesión vs JWT: ¿cuándo cada uno?** La **sesión** guarda el estado en el servidor y la cookie lo identifica: ideal para la web con navegador. El **JWT** es un token firmado que viaja en cada petición (`Authorization: Bearer`): ideal para APIs y apps móviles. Aquí la web usa sesión y la API acepta ambos.
27. **¿Cómo protegiste las fotos y los exámenes?** Se guardan fuera de `static`, sin `MEDIA_URL`; el almacenamiento (`AlmacenamientoPrivado`) ni siquiera tiene `.url`. Solo una vista con login y permisos entrega el archivo, con `Cache-Control: private, no-store`. Nginx no tiene ruta hacia esa carpeta.

**API y Django**

28. **¿Qué hace un `ViewSet` y un router?** El `ViewSet` agrupa list/retrieve/create/update/destroy en una clase; el router genera las URLs. Los permisos por rol están en `PorRol` y el filtrado por objeto en `get_queryset()`.
29. **¿Para qué sirve un serializer?** Convierte modelos ↔ JSON y valida la entrada. Mis serializers delegan en `servicios.py`, así la API aplica las mismas reglas que la web.
30. **¿Cómo comprobaste que todo funciona?** 310 pruebas automatizadas: reglas, constraints reales de PostgreSQL, matriz de permisos rol × ruta (web y API), CSRF, sesión, `check --deploy`, Admin y seed. Más `makemigrations --check` y `spectacular --validate --fail-on-warn`.

---

## 5. Repaso de conceptos (prueba de alternativas)

**ORM (Object-Relational Mapper)** — Traduce clases Python ↔ tablas. `Modelo.objects.filter(...)` genera SQL. *Perezoso*: la consulta se ejecuta al iterar/evaluar. `select_related` (JOIN, para FK) y `prefetch_related` (consulta aparte, para relaciones inversas/M2M) evitan el problema N+1. `F()` referencia columnas; `Q()` arma condiciones con `&`, `|`, `~`.

**Migraciones** — `makemigrations` crea el archivo de cambios; `migrate` los aplica; `showmigrations` los lista. Se versionan en git. Nunca editar una migración ya aplicada en producción.

**Django Admin** — Interfaz automática de gestión. `ModelAdmin`: `list_display`, `list_filter`, `search_fields`, `date_hierarchy`, `readonly_fields`, `inlines`, `actions`. Solo entra quien tiene `is_staff=True`.

**Serializers (DRF)** — Validan y convierten datos. `ModelSerializer` deriva campos del modelo. `read_only` / `write_only`. `SerializerMethodField` calcula un valor.

**ViewSets y routers** — `ModelViewSet` = CRUD completo. `@action` agrega rutas extra. `DefaultRouter` genera las URLs. `get_queryset()` es el punto para filtrar por usuario.

**Permisos** — *Autenticación* = quién eres; *autorización* = qué puedes hacer. En DRF: `permission_classes`; permiso **por objeto** = filtrar el queryset o `has_object_permission`. Códigos: **401** = no autenticado, **403** = autenticado sin permiso, **404** = no existe (o no tienes derecho a saberlo).

**Sesiones vs JWT** — Sesión: id en cookie, datos en el servidor, se invalida borrándola. JWT: token firmado autocontenido (`access` corto + `refresh` largo), el servidor no guarda estado; no se puede "revocar" fácilmente antes de que expire.

**CSRF** — Protege formularios con sesión. Token por formulario. Las APIs con JWT en cabecera no lo necesitan (el navegador no lo manda solo). En este proyecto la sesión en la API sí exige CSRF para métodos de escritura.

**PostgreSQL** — Base relacional con transacciones **ACID**. Tipos de rango, `ExclusionConstraint`, índices GiST. Extensiones (`btree_gist`). Roles y permisos de usuario de base de datos.

**Gunicorn** — Servidor WSGI de producción; *workers* = procesos que atienden peticiones (regla común: 2×núcleos+1). Se ejecuta con systemd.

**Nginx** — Servidor web/proxy inverso: HTTPS, estáticos, `proxy_pass`, límites (`client_max_body_size`). Archivos de configuración en `sites-available` → enlace en `sites-enabled`; `nginx -t` valida.

**EC2** — Máquina virtual de AWS. IP pública (puede cambiar si no es Elastic). Se accede por SSH con un par de llaves.

**Grupos de seguridad** — Firewall virtual de la instancia, **con estado**: define puertos y orígenes permitidos de **entrada**. Principio: abrir solo lo necesario (22 restringido, 80, 443).

**HTTPS / Let's Encrypt** — Cifra el tráfico (TLS). Let's Encrypt emite certificados gratis, válidos 90 días, renovación automática con Certbot. **HSTS** pide al navegador usar siempre https.

**python-decouple y `.env`** — Separa configuración del código. Trampa: `VAR=` (vacía) **no** usa el valor por defecto. El `.env` nunca va a git (`.gitignore`).

**Signals (señales)** — Reaccionan a eventos del ORM (`post_save`). Aquí crean la ficha al crear la mascota.

**Transacción y `select_for_update`** — `transaction.atomic` = todo o nada. `select_for_update` bloquea filas hasta terminar la transacción para evitar carreras.

**Pruebas** — `TestCase` crea una base temporal y revierte cada prueba. Se prueba la regla, el borde y el error esperado, no solo el caso feliz.
