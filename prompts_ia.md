# Registro de apoyos de IA — PetCare (Evaluación 3)

**Estudiante:** Catalina Quezada Sanzana · **Asignatura:** Desarrollo Backend (INACAP) · **Proyecto:** Sistema de Gestión de Citas y Fichas Médicas para Veterinaria (PetCare)

Este documento deja constancia de **cómo usé inteligencia artificial** en el proyecto: qué le pedí, qué obtuve y qué revisé o corregí yo. Las herramientas fueron **Claude (chat)** para analizar el enunciado y **Claude Code** (asistente en el editor) para construir y verificar el código bajo mi dirección.

> **Cómo leer este archivo:** primero la tabla resumen; luego una ficha por cada apoyo (número, fecha, herramienta, objetivo, prompt, resultado, qué revisé/corregí y archivos afectados); al final, mi reflexión. Los textos marcados con ✏️ son datos que solo yo conozco y completo antes de entregar.

---

## Tabla resumen

| N° | Fecha | Herramienta | Objetivo | Archivos principales afectados |
|---|---|---|---|---|
| 1 | ✏️ (antes del 26/10/2026) | Claude (chat) | Analizar el enunciado de la evaluación y la rúbrica; transformarlos en requisitos concretos y en un prompt de trabajo | Ninguno (insumo del prompt 2) |
| 2 | 26/10/2026 | Claude Code | Prompt maestro: construir PetCare completo (4 funcionalidades, roles, API, Admin, seed, pruebas, documentación) | Todo el repositorio |
| 3.1 | 26/10/2026 | Claude Code | Revisar el plan propuesto y aprobarlo con 8 ajustes de diseño | `agenda/models.py`, `clientes/models.py`, `clinica/*`, `core/archivos.py`, `clientes/servicios.py` |
| 3.2 | 26/10/2026 | Claude Code | Corregir la versión de Python del entorno (3.12 para coincidir con Ubuntu 24.04) | `.venv` (local), `requirements.txt` |
| 3.3 | 26/10/2026 | Claude Code | Usar mi rol local `catalina` en vez de `postgres` y documentar ambas opciones de creación de la BD | `crear_bd.sql`, `crear_bd_con_rol_existente.sql`, `README.md` |
| 3.4 | 26/10/2026 | Claude Code | Autorizar el avance por todas las fases sin pedir aprobación intermedia (con condiciones de parada) | Historial de commits |
| 4 | ✏️ (fecha del despliegue) | Claude Code (+ ✏️ chat si lo usé) | Apoyo para el despliegue en AWS EC2: archivos de Nginx, Gunicorn, cron y guía paso a paso | `deploy/*`, `README.md` §10 |

---

## 1. Análisis del enunciado y la rúbrica

| Campo | Detalle |
|---|---|
| **N° / Fecha** | 1 / ✏️ (completar con la fecha de esa conversación) |
| **Herramienta** | Claude (chat) |
| **Objetivo** | Entender qué pide el Proyecto 1 y cómo se evalúa (rúbrica de 5 criterios), y convertirlo en una lista de requisitos verificables para poder pedirle el desarrollo a Claude Code de forma ordenada. |
| **Prompt utilizado** | ✏️ Pegar aquí (textual o resumido) lo que le escribí al chat: el enunciado del proyecto, la rúbrica y mi pedido de análisis. |
| **Resultado obtenido** | Una interpretación de los 5 criterios con el nivel "Excelente" para cada uno (PostgreSQL con restricciones a nivel de base de datos, Django Admin personalizado, CRUD con reglas de negocio, seguridad/sesiones/IA, despliegue y defensa) y la estructura del prompt maestro (entrada 2): roles, funcionalidades, reglas obligatorias, documentación y verificaciones finales. |
| **Qué revisé o corregí yo** | ✏️ Completar (por ejemplo: comprobé cada criterio contra el PDF de la rúbrica; agregué la exigencia de archivos privados; pedí HTTPS detrás de proxy como en la EVA 2…). |
| **Archivos afectados** | Ninguno directamente; el resultado alimentó la entrada 2. |

---

## 2. Prompt maestro en Claude Code

| Campo | Detalle |
|---|---|
| **N° / Fecha** | 2 / 26/10/2026 |
| **Herramienta** | Claude Code (modelo Claude Sonnet 5.5) en VS Code |
| **Objetivo** | Construir el sistema completo en un repositorio nuevo, usando mi EVA 2 solo como referencia de arquitectura y estilo visual, y cumpliendo la rúbrica en nivel "Excelente". |
| **Prompt utilizado** | **Texto completo en el [Anexo A](#anexo-a--prompt-maestro-completo-textual).** Resumen: stack (Python/Django 5.2/DRF/SimpleJWT/drf-spectacular/psycopg 3/decouple/gunicorn, solo PostgreSQL, `America/Santiago`, `es-cl`); roles ADMINISTRADOR, RECEPCIONISTA, VETERINARIO y TUTOR con `is_staff` sincronizado; 4 funcionalidades (tutores y mascotas; agenda con `ExclusionConstraint`; ficha clínica; vacunas y recordatorios); web responsiva con la paleta rosado/café de mi EVA 2; API con JWT y Swagger; Django Admin personalizado; `seed_data` idempotente; pruebas; README, `prompts_ia.md` y `GUIA_DEFENSA.md`; reglas: mostrar `git remote -v` y un plan y **esperar mi aprobación**, commits pequeños en español, **no hacer push** hasta que yo diga "commit y push", cero secretos en el código. |
| **Resultado obtenido** | Un plan por fases que yo revisé (entrada 3.1) y luego la implementación: apps `usuarios`, `clientes`, `agenda`, `clinica`, `vacunacion` y `core`; 312 pruebas automatizadas; Admin con marca PetCare; API documentada sin advertencias; carpeta `deploy/`; y los tres documentos (README, este archivo y la guía de defensa). |
| **Qué revisé o corregí yo** | Pedí ver el plan **antes** de que se escribiera código, lo ajusté (entrada 3.1) y definí el entorno (entradas 3.2 y 3.3). ✏️ Agregar aquí lo que verifiqué al probar la aplicación (flujos por rol, intento de ver datos de otro tutor, solapamiento de citas, etc.). |
| **Archivos afectados** | Todo el repositorio (ver `git log`). |

---

## 3. Correcciones y decisiones que le indiqué durante el desarrollo

### 3.1 Aprobación del plan con ajustes

| Campo | Detalle |
|---|---|
| **N° / Fecha** | 3.1 / 26/10/2026 |
| **Herramienta** | Claude Code |
| **Objetivo** | Corregir el plan propuesto antes de escribir código. |
| **Prompt utilizado (resumido)** | "Apruebo el plan con estos ajustes": (1) mostrar `git remote -v` y confirmar la clonación de `../referencia_eva2` y el uso de su `tema.css`; (2) entorno con `py`, `.venv`, sin Docker; (3) `ATENDIDA` y `NO_ASISTIO` siguen ocupando el horario; (4) **eliminar el correo de `Tutor`** y usar el del `Usuario`; (5) **sin `ExclusionConstraint` en la disponibilidad semanal** (solo validación en el servicio, con pruebas); la restricción queda solo en `Cita`; (6) la atención se puede registrar desde una cita `PROGRAMADA` o `CONFIRMADA` y también **sin cita** (urgencia); (7) **archivos privados** (adjuntos de exámenes y fotos) servidos solo por una vista protegida, con pruebas 403/404 y aviso en el README para Nginx; (8) la API expone los archivos como URL a esa vista, nunca como ruta de media. |
| **Resultado obtenido** | Se aplicaron los 8 ajustes: `Tutor` sin campo `correo`; validación de solape de disponibilidad en `agenda/servicios.py` (con pruebas); `Atencion.cita` opcional; `core/archivos.py` (`AlmacenamientoPrivado` sin URL pública) y vistas `mascota_foto` / `examen_archivo`; acciones `/foto/` y `/archivo/` en la API; sección 10.7 del README. |
| **Qué revisé o corregí yo** | Yo pedí eliminar el correo duplicado (una sola fuente de verdad), evitar una `ExclusionConstraint` sobre horas porque complicaría el despliegue y exigir archivos privados por tratarse de datos clínicos. |
| **Archivos afectados** | `clientes/models.py`, `agenda/models.py`, `agenda/servicios.py`, `clinica/models.py`, `clinica/servicios.py`, `core/archivos.py`, `clientes/views.py`, `clinica/views.py`, `*/api.py`, `README.md`. |

### 3.2 Versión de Python del entorno

| Campo | Detalle |
|---|---|
| **N° / Fecha** | 3.2 / 26/10/2026 |
| **Herramienta** | Claude Code |
| **Objetivo** | Que el entorno local coincida con el servidor (Ubuntu 24.04 trae Python 3.12). |
| **Prompt utilizado (resumido)** | "Sí, recrea el `.venv` con Python 3.12 (`py -3.12`), verifica con `python --version` y `python manage.py check`, y continúa." (Antes yo había indicado Python 3.14; la IA me advirtió que existía la 3.12 y que coincidía con el servidor.) |
| **Resultado obtenido** | `.venv` recreado con Python 3.12.0; `requirements.txt` instalado y `check` sin problemas. |
| **Qué revisé o corregí yo** | Decidí priorizar la paridad local/servidor sobre la versión más nueva. |
| **Archivos afectados** | `.venv/` (no versionado). |

### 3.3 Base de datos local con mi rol `catalina`

| Campo | Detalle |
|---|---|
| **N° / Fecha** | 3.3 / 26/10/2026 |
| **Herramienta** | Claude Code |
| **Objetivo** | Poder crear la base sin la contraseña del superusuario `postgres`. |
| **Prompt utilizado (resumido)** | "No tengo la contraseña de `postgres`, por eso el rol `petcare` nunca se creó. Tengo el rol local `catalina` con `CREATEDB`. Crea la base con dueño `catalina`, activa `btree_gist` como dueño (extensión *trusted*), deja el `.env` local con ese rol y documenta **ambas opciones** (con superusuario o con un rol con `CREATEDB`). En AWS se usará otro usuario y otra contraseña." |
| **Resultado obtenido** | Base `petcare_db` creada con dueño `catalina`, `btree_gist` activada y conexión verificada; nuevo script `crear_bd_con_rol_existente.sql`; `crear_bd.sql` queda como opción A (la contraseña se pasa por variable de `psql`, nunca escrita en el repositorio); ambas opciones documentadas en el README. |
| **Qué revisé o corregí yo** | Detecté el problema de credenciales, ofrecí la alternativa y pedí que no quedara ninguna contraseña en el repositorio. |
| **Archivos afectados** | `crear_bd.sql`, `crear_bd_con_rol_existente.sql`, `README.md` §4.1, `.env` (local, no versionado). |

### 3.4 Avance autónomo por fases

| Campo | Detalle |
|---|---|
| **N° / Fecha** | 3.4 / 26/10/2026 |
| **Herramienta** | Claude Code |
| **Objetivo** | Acelerar la construcción sin perder control. |
| **Prompt utilizado (resumido)** | "Avanza por TODAS las fases restantes sin detenerte a pedir aprobación; haz un commit local por fase (sin push) y verifica `check` y `test` antes de cada commit. Detente solo si hay un error que no puedes resolver, necesitas que escriba algo (una contraseña) o una decisión cambia algo importante del plan aprobado. Al final entrégame el resumen y espera «commit y push»." |
| **Resultado obtenido** | Fases 3 a 12 construidas con commits locales en español; ningún push realizado. |
| **Qué revisé o corregí yo** | Mantuve el control del push y de las decisiones de diseño. ✏️ Anotar si revisé los commits uno por uno. |
| **Archivos afectados** | Historial de git. |

### 3.5 Hallazgos técnicos que las pruebas obligaron a corregir (durante el desarrollo)

Estos problemas aparecieron al ejecutar las pruebas y se corrigieron en el código; los dejo como evidencia de que **no acepté el código sin verificarlo**:

| Hallazgo | Corrección |
|---|---|
| El almacenamiento de archivos privados fijaba su carpeta al importar el módulo, así que las pruebas escribían en la carpeta real. | `AlmacenamientoPrivado` lee `ARCHIVOS_PRIVADOS_ROOT` en cada uso y no tiene `.url`. |
| `ClearableFileInput` (formularios y Admin) intenta mostrar `foto.url`, que no existe para archivos privados. | Se usan `FileInput` en los formularios y en el Admin. |
| El Admin de `Cita` fallaba al validar la `ExclusionConstraint` porque el campo `estado` (de la condición) no está en el formulario. | El formulario del Admin incluye `estado` en las exclusiones de validación. |
| El rol ADMINISTRADOR no tenía permisos de modelo en el Admin (solo `is_staff`). | `Usuario.has_perm` / `has_module_perms` conceden todo al rol. |
| Mensajes de error inconsistentes cuando una cita caía fuera del horario o en el pasado. | Se valida primero "pasado" y se unifica el mensaje de "no atiende en ese horario". |
| El validador automático de unicidad de DRF exigía `profesional` en el cuerpo de la disponibilidad del veterinario. | Se desactiva en ese serializer y se valida el solape en el servicio. |
| Pruebas dependientes de la hora del día (citas "de hoy"). | Se fijan a las 12:00 hora de Santiago. |

---

## 4. Apoyo para el despliegue en AWS

| Campo | Detalle |
|---|---|
| **N° / Fecha** | 4 / ✏️ (fecha del despliegue) |
| **Herramienta** | Claude Code (archivos y guía) · ✏️ Claude chat, si lo usé durante el despliegue |
| **Objetivo** | Dejar listo y documentado el despliegue en EC2 (Ubuntu 24.04): PostgreSQL, Gunicorn como servicio, Nginx con HTTPS (Let's Encrypt) en `codelab-catalina.duckdns.org` (IP `54.152.231.63`), cron de recordatorios y grupo de seguridad. |
| **Prompt utilizado** | Parte del prompt maestro (entrada 2): "Nginx pasa `X-Forwarded-Proto` con `include proxy_params`", variables `DETRAS_DE_PROXY_HTTPS` y `CSRF_TRUSTED_ORIGINS`, README con despliegue y archivos privados que Nginx no debe exponer. ✏️ Agregar los prompts adicionales que use durante el despliegue real. |
| **Resultado obtenido** | `deploy/nginx-petcare.conf`, `deploy/gunicorn-petcare.service`, `deploy/cron-recordatorios`, `deploy/env.produccion.ejemplo` y la sección 10 del README (pasos, tabla del grupo de seguridad y tabla de problemas frecuentes). `python manage.py check --deploy` sin advertencias con las variables de producción simuladas (prueba automatizada). |
| **Qué revisé o corregí yo** | ✏️ Completar tras el despliegue: errores reales que aparecieron (502, 400 por `ALLOWED_HOSTS`, CSRF, permisos de `archivos_privados/`…), cómo los resolví y qué ajusté en los archivos de `deploy/`. |
| **Archivos afectados** | `deploy/*`, `README.md` §10. |

---

## Reflexión

> ✏️ *Borrador para que lo adaptes con tus propias palabras antes de entregar.*

**Lo que aprendí**

1. **Las reglas importantes se defienden en dos capas.** Validar en Python da mensajes claros, pero solo la base de datos garantiza la regla cuando dos personas actúan a la vez. Por eso el solape de citas tiene un servicio *y* una `ExclusionConstraint`.
2. **La lógica de negocio va en `servicios.py`, no en las vistas.** Así la web, la API, el Admin y el seed comparten la misma regla y no se puede esquivar entrando por otra puerta.
3. **Seguridad de datos clínicos es más que el login.** Hay que pensar en el *objeto* (un tutor no ve lo de otro: 404), en los *archivos* (no deben estar en `/media/`) y en el *servidor* (Nginx no debe exponer esa carpeta).
4. **Las pruebas encuentran lo que uno no ve.** Varias fallas (archivos privados, Admin y constraints, permisos del rol administrador) aparecieron solo al ejecutarlas.
5. **Configuración fuera del código.** `python-decouple` y `.env` evitan secretos en el repositorio; y una variable *vacía* no usa el valor por defecto.

**Cómo usé la IA y qué cuidé**

- La usé como **asistente que acelera**, no como reemplazo: yo definí el problema, revisé el plan antes de que se escribiera código, tomé las decisiones de diseño (entrada 3.1) y mantuve el control de cuándo se sube algo al repositorio.
- Exigí **verificación**: pruebas automatizadas, `check`, `check --deploy`, `makemigrations --check` y la validación del esquema OpenAPI.
- Debo poder **explicar y defender cada parte** del código; para eso preparé `GUIA_DEFENSA.md` y revisé el código de cada servicio.

**Qué haría distinto / próximos pasos**

- Agregar pruebas de carga y de concurrencia reales sobre la reserva de horarios.
- Enviar los recordatorios por un canal real (SMTP o WhatsApp) y programar la ejecución con un supervisor.
- Agregar auditoría completa (quién vio cada ficha) y respaldos automáticos de la base de datos y de `archivos_privados/`.

---

## Anexo A — Prompt maestro completo (textual)

<details>
<summary>Ver el prompt completo de la entrada 2</summary>

```text
Contexto: soy estudiante de INACAP, asignatura Desarrollo Backend, EVALUACIÓN 3 (individual). Me tocó el "Proyecto 1: Sistema de Gestión de Citas y Fichas Médicas para Veterinaria (PetCare)". Problema: solapamiento de citas, pérdida de fichas clínicas en papel y falta de seguimiento de vacunas. El proyecto se desplegará en una instancia AWS EC2 (Ubuntu 24.04) con Nginx + Gunicorn + PostgreSQL, detrás de HTTPS con Let's Encrypt en codelab-catalina.duckdns.org (IP pública 54.152.231.63). Nginx pasa X-Forwarded-Proto con "include proxy_params". Esta carpeta es un repositorio NUEVO y vacío: https://github.com/Catalin406/petcare-eva3.git

REFERENCIA (mi EVA 2, ya evaluada): clónala FUERA de esta carpeta, en ../referencia_eva2, desde https://github.com/Catalin406/BACKEND_2.git. Úsala SOLO como referencia de arquitectura y estilo; no la modifiques ni copies su dominio (cursos/matrículas). Reutiliza de ella: la estructura de settings.py con python-decouple y .env, el patrón de roles con is_staff sincronizado en Usuario.save(), servicios.py separados de las vistas, bloqueos select_for_update, seed_data idempotente, el estilo de comentarios por bloques en español, el soporte HTTPS detrás de proxy (DETRAS_DE_PROXY_HTTPS, CSRF_TRUSTED_ORIGINS) y, MUY IMPORTANTE, la paleta y el diseño visual de static/css/tema.css (rosados y café pastel: --color-principal #f4a7b9, principal-suave #fbd3dd, principal-oscuro #c9627d, secundario #dcc6ad, secundario-suave #f1e6d9, acento #b08968, acento-oscuro #7f5c42, fondo #fff4f7, texto #4a3b36, texto-suave #7a6660, borde #f0d9df), la misma tipografía y Bootstrap 5.3 con Bootstrap Icons. El sitio nuevo debe verse de la misma familia visual.

REGLAS OBLIGATORIAS:
1. Primero ejecuta "git remote -v" y muéstramelo. Luego muéstrame un plan en español (apps, modelos con campos y relaciones, reglas de negocio, rutas web y API, permisos por rol) y ESPERA mi aprobación antes de escribir código.
2. NO hagas push hasta que yo diga "commit y push". Trabaja en commits pequeños por fase con mensajes en español.
3. Cero secretos en el código: todo configurable por .env (SECRET_KEY, DEBUG, ALLOWED_HOSTS, DB_*, CSRF_TRUSTED_ORIGINS, DETRAS_DE_PROXY_HTTPS). Con python-decouple, una variable presente pero vacía NO cae al default: documéntalo en .env.example.
4. Stack: Python 3.12, Django 5.2 LTS, Django REST Framework, djangorestframework-simplejwt, drf-spectacular, psycopg 3, python-decouple, gunicorn (incluido en requirements.txt con versiones fijas). Base de datos SOLO PostgreSQL (nada de SQLite). Zona horaria America/Santiago, idioma es-cl.
5. Comentarios y nombres en español, explicando el porqué. Lógica de negocio en servicios.py, nunca en las vistas.
6. Todo debe quedar probado con pruebas automatizadas que pasen.

ESTA EVALUACIÓN SE CORRIGE CON UNA RÚBRICA. Cada punto debe quedar en nivel "Excelente":
- Criterio 1 (PostgreSQL): conexión íntegra por variables de entorno, migraciones limpias (makemigrations --check sin cambios), datos relacionales con ForeignKey/OneToOne, on_delete pensado, y restricciones a nivel de base de datos (UniqueConstraint, CheckConstraint y la ExclusionConstraint descrita abajo).
- Criterio 2 (Django Admin): TODOS los modelos registrados y personalizados: list_display con columnas útiles, list_filter, search_fields, date_hierarchy donde haya fechas, inlines (mascotas dentro del tutor; recetas y exámenes dentro de la atención), readonly_fields de auditoría, acciones masivas útiles, insignias de color con format_html para los estados, y PLANTILLAS de admin personalizadas (templates/admin/base_site.html y un CSS propio) con la marca PetCare y la paleta rosado/café. site_header, site_title e index_title en español.
- Criterio 3 (CRUD y reglas): CRUD completo (web y API) y la lógica de negocio de las 4 funcionalidades descritas abajo, impecable y validada.
- Criterio 4 (seguridad, sesiones e IA): autenticación con LoginView/LogoutView (logout por POST), sesiones con expiración configurable, TODA la aplicación web exige login (aquí hay datos clínicos: nada de lectura pública), permisos por rol en vistas HTML y en la API (JWT), control de acceso a nivel de objeto (un tutor jamás ve datos de otro tutor: pruebas que lo demuestren), validadores de contraseña, cookies seguras activables por .env, CSRF intacto. Además, archivo prompts_ia.md (ver abajo).
- Criterio 5 (despliegue y defensa): README.md con instrucciones claras de ejecución local y despliegue, la IP pública 54.152.231.63 y la URL https://codelab-catalina.duckdns.org, y credenciales de demostración. Además, GUIA_DEFENSA.md (ver abajo).

ROLES (Usuario personalizado con campo rol; is_staff se sincroniza solo para ADMINISTRADOR):
- ADMINISTRADOR: todo, incluido Django Admin.
- RECEPCIONISTA: gestiona tutores, mascotas y citas; NO edita fichas clínicas.
- VETERINARIO: ve su agenda, atiende citas y escribe en la ficha clínica; define su disponibilidad.
- TUTOR: solo ve SUS mascotas, SUS citas, la ficha de SUS mascotas (solo lectura) y SUS recordatorios; puede solicitar y cancelar citas propias con anticipación mínima configurable.

LAS 4 FUNCIONALIDADES (con su lógica de negocio):

1) CRUD y administración de Tutores y Mascotas.
- Tutor (vinculado a un Usuario con rol TUTOR): RUT chileno validado con dígito verificador y único, teléfono, dirección, correo.
- Mascota: tutor (FK), nombre, especie (choices), raza, sexo, fecha de nacimiento (no futura), peso, color/señas, microchip opcional único, foto opcional, activa. La edad se calcula. No se elimina una mascota con historial clínico: se desactiva.

2) Calendario/agendamiento con disponibilidad por profesional.
- Profesional (Usuario VETERINARIO) con especialidad.
- DisponibilidadSemanal: profesional, día de la semana, hora_inicio, hora_fin, duración del bloque en minutos (sin solapes entre bloques del mismo profesional).
- BloqueoAgenda opcional (vacaciones/feriados).
- Cita: mascota, profesional, inicio, fin, motivo, estado (PROGRAMADA, CONFIRMADA, ATENDIDA, CANCELADA, NO_ASISTIO), creada_por, historial de cambios.
- Reglas: no en el pasado; debe caer completa dentro de la disponibilidad del profesional y fuera de bloqueos; NO puede solaparse con otra cita activa del mismo profesional NI de la misma mascota. Garantízalo en dos capas: validación amable en servicios.py (mensaje claro) Y una ExclusionConstraint de PostgreSQL con tstzrange y la extensión btree_gist (BtreeGistExtension en la migración; django.contrib.postgres en INSTALLED_APPS), que excluya solo citas no canceladas. Transiciones de estado válidas definidas en un diccionario.
- Servicio que calcula los horarios libres de un profesional para un día.
- Vista de calendario web (FullCalendar desde CDN o equivalente) que consume la API por fetch (enmascaramiento asíncrono) y muestra horarios libres y ocupados por profesional.

3) Ficha clínica digital.
- FichaClinica: OneToOne con Mascota (se crea sola al crear la mascota): alergias, antecedentes, observaciones.
- Atencion: ficha, cita (OneToOne opcional), veterinario, fecha, anamnesis, peso registrado, temperatura, diagnóstico, tratamiento, observaciones. Al registrar la atención de una cita, la cita pasa a ATENDIDA en la misma transacción.
- Receta: atención (FK), medicamento, dosis, frecuencia, duración, indicaciones.
- Examen: atención (FK), tipo, fecha, resultado, archivo adjunto opcional (validar extensión y tamaño).
- Solo VETERINARIO crea/edita atenciones; nadie borra atenciones (registro clínico); la ficha se ve como línea de tiempo.

4) Recordatorios de vacunación y controles periódicos.
- Vacuna (catálogo): nombre, especie aplicable, periodicidad en días.
- RegistroVacuna: mascota, vacuna, fecha de aplicación, lote, veterinario; proxima_dosis se calcula sola con la periodicidad.
- ControlPeriodico: mascota, motivo, fecha_programada.
- Recordatorio: mascota, tipo (VACUNA/CONTROL), fecha_objetivo, estado (PENDIENTE, ENVIADO, COMPLETADO, VENCIDO), canal.
- Comando de gestión "generar_recordatorios" idempotente: crea recordatorios para vacunas y controles que vencen en los próximos N días (N por .env, default 30), marca VENCIDO lo que pasó de fecha y "envía" un correo (EMAIL_BACKEND de consola por defecto) al tutor.
- Panel web de recordatorios: vencidos, próximos 7 días y próximos 30 días, con colores de urgencia; el tutor ve solo los suyos.

INTERFAZ WEB: templates Django responsivos (Bootstrap 5.3 + tema.css adaptado de la referencia), navbar según rol, inicio con resumen por rol (ej. citas de hoy para el veterinario), formularios con mensajes de error claros, páginas 403/404/500 propias con el mismo diseño, footer con el nombre del estudiante leído de .env (ALUMNO_NOMBRE="Catalina Quezada Sanzana").

API: DRF con ViewSets y routers bajo /api/, autenticación JWT (/api/auth/token/ y refresh) más sesión, permisos por rol y por objeto, paginación, filtros, documentación Swagger en /api/docs/ (spectacular --validate --fail-on-warn sin advertencias).

SEED: comando seed_data idempotente con: 1 administrador, 1 recepcionista, 2 veterinarios con disponibilidad, 3 tutores con 2 mascotas cada uno, citas pasadas atendidas con ficha completa (recetas y exámenes), citas futuras, vacunas con próximas dosis variadas (algunas vencidas, algunas en 7 y en 30 días) y recordatorios generados. Al final imprime las credenciales de demostración.

PRUEBAS (deben pasar todas): solapamiento por profesional y por mascota rechazado (servicio y constraint), cita fuera de disponibilidad rechazada, cita en el pasado rechazada, transiciones inválidas rechazadas, atención marca la cita ATENDIDA, próxima dosis calculada, comando generar_recordatorios idempotente, permisos por rol (recepcionista no edita ficha, tutor no ve mascotas ajenas en web ni en API: 403/404), login requerido en todas las vistas, validación de RUT.

DOCUMENTACIÓN:
- README.md: descripción, stack, cómo ejecutar en local, variables de entorno, cómo desplegar en EC2 (Nginx + Gunicorn + PostgreSQL), IP pública y URL, credenciales de demo, cómo correr pruebas.
- prompts_ia.md BIEN ESTRUCTURADO (la rúbrica lo evalúa): una tabla resumen y luego una entrada por cada apoyo de IA con: número, fecha, herramienta (Claude chat / Claude Code), objetivo, prompt utilizado (textual o resumido), resultado obtenido, qué revisé o corregí yo, y archivos afectados. Incluye como entradas: (1) el análisis del enunciado y la rúbrica con Claude chat, (2) este prompt completo, (3) las correcciones que yo te pida durante el desarrollo, (4) el apoyo para el despliegue en AWS. Deja una sección final "Reflexión" con lo aprendido.
- GUIA_DEFENSA.md: explicación simple de la arquitectura (navegador → Nginx → Gunicorn → Django → PostgreSQL), cómo se cumple cada criterio de la rúbrica con rutas y archivos concretos, el guion de demostración en vivo paso a paso (qué mostrar en la web y en el Django Admin), y 30 preguntas probables de defensa con sus respuestas, más un repaso de conceptos para una prueba de alternativas (ORM, migraciones, Admin, serializers, ViewSets, permisos, sesiones vs JWT, CSRF, PostgreSQL, Gunicorn, Nginx, EC2, grupos de seguridad).

AL TERMINAR: ejecuta check, check --deploy (con las variables de producción simuladas), makemigrations --check, spectacular --validate --fail-on-warn y test. Muéstrame los resultados, la lista de commits, las variables que debo poner en el .env del servidor y las credenciales de demo. Luego espera "commit y push".
```

</details>
