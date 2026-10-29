# Registro de uso de IA — PetCare (Evaluación 3)

**Estudiante:** Catalina Quezada Sanzana · **Asignatura:** Desarrollo Backend (INACAP) · **Proyecto:** Sistema de Gestión de Citas y Fichas Médicas para Veterinaria (PetCare)

Aquí cuento, de forma simple, **cómo usé inteligencia artificial** en este proyecto: qué le pedí, qué me respondió y qué revisé o corregí yo. Usé dos herramientas:

- **Claude (chat):** para entender el enunciado y la rúbrica.
- **Claude Code** (el asistente dentro del editor): para construir el código y probarlo, siempre bajo mis instrucciones.

> **Cómo leer este archivo:** primero está la tabla resumen. Después hay una ficha por cada uso de la IA, con lo que pedí, lo que salió, lo que revisé yo y los archivos que cambiaron. Al final está mi reflexión y, en el anexo, el prompt completo. 

---

## Tabla resumen

| N° | Fecha | Herramienta | Qué se hizo | Archivos principales |
|---|---|---|---|---|
| 1 | 26/10/2026 | Claude (chat) | Entender el enunciado y la rúbrica y convertirlos en una lista de requisitos | Ninguno (sirvió para armar el prompt 2) |
| 2 | 26/10/2026 | Claude Code | Prompt principal: construir PetCare completo | Todo el proyecto |
| 3.1 | 26/10/2026 | Claude Code | Revisar el plan y aprobarlo con 8 cambios míos | `clientes/`, `agenda/`, `clinica/`, `core/archivos.py` |
| 3.2 | 26/10/2026 | Claude Code | Cambiar el entorno a Python 3.12 (el mismo del servidor) | `.venv` (solo local) |
| 3.3 | 26/10/2026 | Claude Code | Crear la base con mi usuario `catalina` y documentar dos formas de hacerlo | `crear_bd*.sql`, `README.md` |
| 3.4 | 26/10/2026 | Claude Code | Dejar que avanzara solo por todas las fases, con límites claros | Commits |
| 3.5 | 26 al 28/10/2026 | Claude Code | Problemas que aparecieron al probar y cómo se arreglaron | Varios (ver tabla 3.5) |
| 3.6 | 27/10/2026 | Claude Code | Antes de subir: Swagger con login y `ALLOWED_HOSTS` con `localhost` | `config/urls.py`, `deploy/`, `README.md` |
| 3.7 | 28/10/2026 | Claude Code | Pedí una revisión completa contra el enunciado y la rúbrica | Calendario y documentos |
| 3.8 | 28/10/2026 | Claude Code | Cerrar los huecos que dejó esa revisión (CRUD en la web) | `vacunacion/`, `agenda/`, plantillas |
| 4 | 28/10/2026 | Claude Code (y 28/10/2026 chat, si lo usé) | Ayuda con el despliegue en AWS | `deploy/*`, `README.md` §10 |

---

## 1. Entender el enunciado y la rúbrica

| Campo | Detalle |
|---|---|
| **N° / Fecha** | 1 / 26/10/2026 (la fecha de esa conversación) |
| **Herramienta** | Claude (chat) |
| **Para qué** | Entender qué pide el Proyecto 1 y cómo me van a evaluar (los 5 criterios), y pasarlo a una lista clara de cosas por hacer para después pedírselas a Claude Code en orden. |
| **Qué le pedí** | Subí el enunciado de la Evaluación 3 (`EVA_3_Backend.docx`) con la rúbrica y le pedí que me ayudara a armar el plan de acción y el prompt para Claude Code. Para que quedara exactamente como lo necesitaba, le pedí que cubriera el nivel máximo de cada criterio de la rúbrica y que mantuviera la misma línea estética de mi EVA 2, con la paleta de tonos rosados y café. |
| **Qué salió** | Una explicación de lo que significa "Excelente" en cada criterio (base de datos con reglas, Admin personalizado, CRUD con reglas del caso, seguridad y sesiones, despliegue y defensa). Además, me entregó los roles, las 4 funcionalidades clave con sus reglas de negocio, una tabla detallada para cumplir la rúbrica y el prompt listo. Con eso armé el prompt principal de la entrada 2. |
| **Qué revisé o corregí yo** | Tuve que corregir varias cosas sobre la marcha:<br>• Aclaré bien los colores y excluí Webpay, porque el profesor avisó que no se evaluaba.<br>• Revisando el plan de Claude Code, pedí ajustar 4 puntos críticos: que los archivos clínicos quedaran protegidos por una vista con permisos, quitar la restricción de solape en la disponibilidad semanal, usar solo el correo del usuario y permitir atenciones sin cita.<br>• No recordaba la contraseña del superusuario de PostgreSQL, y lo resolví usando el usuario local `catalina` de mi EVA 2.<br>• Pedí proteger Swagger con inicio de sesión y corregir el número de pruebas en la documentación, para que todo quedara impecable. |
| **Archivos** | Ninguno. |   

---

## 2. Prompt principal en Claude Code

| Campo | Detalle |
|---|---|
| **N° / Fecha** | 2 / 26/10/2026 |
| **Herramienta** | Claude Code (modelo Claude Sonnet 5.5) en VS Code |
| **Para qué** | Construir todo el sistema en un repositorio nuevo, usando mi EVA 2 solo como guía de orden y de estilo visual, y cumpliendo la rúbrica en nivel "Excelente". |
| **Qué le pedí** | El texto completo está en el [Anexo A](#anexo-a--prompt-principal-completo-textual). En corto: Django 5.2 con API, solo PostgreSQL, cuatro roles (administrador, recepcionista, veterinario y tutor), las 4 funcionalidades del caso, la misma paleta rosado y café de mi EVA 2, Admin personalizado, datos de ejemplo, pruebas automáticas, y tres documentos (README, este archivo y la guía de defensa). Reglas: que me mostrara un plan y **esperara mi aprobación**, que no subiera nada hasta que yo dijera "commit y push", y que no dejara claves en el código. |
| **Qué salió** | Primero un plan por fases, que yo revisé (entrada 3.1). Después el sistema: las apps `usuarios`, `clientes`, `agenda`, `clinica`, `vacunacion` y `core`, más de 300 pruebas automáticas, el Admin con la marca PetCare, la API documentada y la carpeta `deploy/`. |
| **Qué revisé o corregí yo** | Pedí ver el plan **antes** de que se escribiera código, lo cambié (entrada 3.1) y decidí cómo sería mi entorno (entradas 3.2 y 3.3). 
| **Archivos** | Todo el repositorio (ver `git log`). |

---

## 3. Lo que le corregí o le pedí durante el trabajo

### 3.1 Aprobé el plan, pero con cambios

| Campo | Detalle |
|---|---|
| **N° / Fecha** | 3.1 / 26/10/2026 |
| **Herramienta** | Claude Code |
| **Para qué** | Arreglar el plan antes de que se escribiera código. |
| **Qué le pedí (resumido)** | "Apruebo el plan con estos cambios": (1) que mostrara `git remote -v` y confirmara que clonó mi EVA 2 y que usaría su `tema.css`; (2) entorno con `py` y `.venv`, sin Docker; (3) las citas atendidas y las de "no asistió" siguen ocupando el horario; (4) **quitar el correo del Tutor** y usar el del Usuario; (5) **no usar la restricción de PostgreSQL en la disponibilidad semanal**, solo validarla en el servicio y con pruebas; (6) poder registrar una atención desde una cita **o sin cita** (urgencia); (7) **fotos y exámenes privados**: solo se entregan con una vista que revisa login y permisos, con pruebas, y avisar en el README que Nginx no debe mostrar esa carpeta; (8) que la API dé esos archivos como una dirección protegida, nunca como una ruta pública. |
| **Qué salió** | Se aplicaron los 8 cambios: Tutor sin campo de correo; el solape de horarios se valida en `agenda/servicios.py` (con pruebas); la atención puede no tener cita; archivos privados en `core/archivos.py` con sus vistas protegidas; y la sección 10.7 del README. |
| **Qué revisé o corregí yo** | Pedí quitar el correo repetido (así hay una sola fuente de verdad), evitar la restricción con horas porque complicaba el despliegue, y proteger los archivos porque son datos clínicos. |
| **Archivos** | `clientes/models.py`, `agenda/models.py`, `agenda/servicios.py`, `clinica/*`, `core/archivos.py`, `*/api.py`, `README.md`. |

### 3.2 Cambio de versión de Python

| Campo | Detalle |
|---|---|
| **N° / Fecha** | 3.2 / 26/10/2026 |
| **Herramienta** | Claude Code |
| **Para qué** | Que mi computador use la misma versión que el servidor (Ubuntu 24.04 trae Python 3.12). |
| **Qué le pedí (resumido)** | "Sí, vuelve a crear el `.venv` con Python 3.12, comprueba la versión y sigue." Yo había dicho Python 3.14, pero la IA me avisó que tenía la 3.12 instalada y que era la del servidor. |
| **Qué salió** | `.venv` nuevo con Python 3.12.0 y `check` sin errores. |
| **Qué revisé o corregí yo** | Preferí que mi computador y el servidor fueran iguales antes que usar la versión más nueva. |
| **Archivos** | Ninguno (el `.venv` no se sube). |

### 3.3 Base de datos con mi usuario `catalina`

| Campo | Detalle |
|---|---|
| **N° / Fecha** | 3.3 / 26/10/2026 |
| **Herramienta** | Claude Code |
| **Para qué** | Poder crear la base sin la clave del usuario `postgres`, que no tengo. |
| **Qué le pedí (resumido)** | "No tengo la clave de `postgres`. Tengo mi usuario `catalina` con permiso para crear bases. Crea la base con ese usuario, activa `btree_gist`, deja mi `.env` con esos datos y escribe en la documentación las dos formas de hacerlo. En AWS usaré otro usuario y otra clave." |
| **Qué salió** | Base `petcare_db` creada y probada; un script nuevo (`crear_bd_con_rol_existente.sql`); `crear_bd.sql` como la otra opción (la clave se escribe al ejecutarlo, no queda en el repositorio); ambas formas explicadas en el README. |
| **Qué revisé o corregí yo** | Me di cuenta del problema con la clave, propuse la alternativa y pedí que ninguna contraseña quedara escrita en el repositorio. |
| **Archivos** | `crear_bd.sql`, `crear_bd_con_rol_existente.sql`, `README.md` §4.1. |

### 3.4 Avanzar solo por todas las fases

| Campo | Detalle |
|---|---|
| **N° / Fecha** | 3.4 / 26/10/2026 |
| **Herramienta** | Claude Code |
| **Para qué** | Avanzar más rápido sin perder el control. |
| **Qué le pedí (resumido)** | "Sigue con todas las fases sin pedirme permiso cada vez. Haz un commit por fase, sin subir nada, y prueba antes de cada commit. Para solo si hay un error que no puedes resolver, si necesitas que yo escriba algo (como una clave) o si algo cambia el plan. Al final muéstrame el resumen y espera mi 'commit y push'." |
| **Qué salió** | Las fases 3 a 11 hechas, cada una con su commit en español y sin ningún push. |
| **Qué revisé o corregí yo** | Me quedé con el control de cuándo se sube el código y de las decisiones de diseño.|
| **Archivos** | Historial de git. |

### 3.5 Problemas que aparecieron al probar y cómo se arreglaron

Esto muestra que **no acepté el código sin revisarlo**: cada problema salió al correr las pruebas o al revisar, y se corrigió.

| Qué pasaba | Cómo se arregló |
|---|---|
| Los archivos privados se guardaban siempre en la carpeta real, incluso en las pruebas. | Ahora la carpeta se lee de la configuración cada vez, y esos archivos no tienen dirección pública. |
| Los formularios y el Admin intentaban mostrar la dirección de la foto, que no existe porque es privada. | Se cambió el tipo de campo de archivo. |
| El Admin fallaba al validar el horario de una cita. | El formulario del Admin ahora incluye el estado en esa validación. |
| El rol Administrador no podía usar ningún modelo del Admin (solo tenía permiso de entrar). | Ahora ese rol tiene todos los permisos. |
| Los mensajes de error de una cita en el pasado o fuera de horario eran confusos. | Se revisa primero el pasado y se unificó el mensaje de "no atiende en ese horario". |
| La API pedía el campo "profesional" aunque el veterinario ya era el dueño de su horario. | Se quitó esa exigencia y el solape se revisa en el servicio. |
| Algunas pruebas dependían de la hora del día. | Se fijaron a las 12:00 hora de Santiago. |
| El calendario cargaba dos archivos de FullCalendar desde direcciones que no existen (error 404): sin eso quedaba en inglés. | Se corrigieron las direcciones (ver 3.7). |
| Borrar un profesional con historial por la API daba error 500. | Ahora se desactiva, igual que en la web (ver 3.8). |

### 3.6 Ajustes antes de subir el proyecto

| Campo | Detalle |
|---|---|
| **N° / Fecha** | 3.6 / 27/10/2026 |
| **Herramienta** | Claude Code |
| **Para qué** | Dejar todo coherente con la regla "todo exige iniciar sesión" y con las pruebas desde el servidor. |
| **Qué le pedí (resumido)** | (1) Que `/api/docs/` y `/api/schema/` pidieran sesión iniciada, con una prueba que lo demuestre. (2) Que `ALLOWED_HOSTS` del servidor incluyera `localhost` y `127.0.0.1` para probar con `curl`. (3) Que corriera todas las verificaciones y solo subiera si todo pasaba. |
| **Qué salió** | Sin sesión, esas dos direcciones llevan al login; los endpoints de la API siguen respondiendo 401. `ALLOWED_HOSTS` actualizado en `deploy/env.produccion.ejemplo` y en el README. Todo pasó y se subió. |
| **Qué revisé o corregí yo** | Yo detecté que la documentación de la API estaba abierta a cualquiera, y puse la condición de no subir nada si algo fallaba. |
| **Archivos** | `config/urls.py`, `core/test_seguridad.py`, `deploy/env.produccion.ejemplo`, `README.md`. |

### 3.7 Revisión completa contra el enunciado y la rúbrica

| Campo | Detalle |
|---|---|
| **N° / Fecha** | 3.7 / 28/10/2026 |
| **Herramienta** | Claude Code |
| **Para qué** | Saber con evidencia si el proyecto cumple todo lo que piden, antes de la defensa. |
| **Qué le pedí (resumido)** | "Haz una revisión completa del proyecto y dime si cumple con el caso, los 4 requerimientos y los 5 criterios de la rúbrica." |
| **Qué salió** | Recorrió 73 pantallas con los 4 roles (sin errores), y encontró **un error real** (el idioma y los estilos del calendario apuntaban a direcciones que no existen) y **varios huecos de CRUD en la web**. También me dijo con claridad lo que no estaba hecho: el despliegue en AWS y las partes de este archivo que solo yo puedo completar. |
| **Qué revisé o corregí yo** | Decidí cerrar los huecos (entrada 3.8) y no esconder lo pendiente. |
| **Archivos** | `templates/agenda/calendario.html`. |

### 3.8 Cerrar los huecos de la revisión

| Campo | Detalle |
|---|---|
| **N° / Fecha** | 3.8 / 28/10/2026 |
| **Herramienta** | Claude Code |
| **Para qué** | Que cada cosa tenga su CRUD completo también en la web. |
| **Qué le pedí (resumido)** | "Corrige los huecos y haz el push." |
| **Qué salió** | Las vacunas aplicadas ahora se pueden corregir (se recalcula la próxima dosis) y el administrador puede eliminarlas; los controles periódicos se pueden eliminar; y hay pantallas para gestionar profesionales (si tienen historial, se desactivan en vez de borrarse). 22 pruebas nuevas; en total **334 pruebas, todas pasan**. Las recetas y los exámenes siguen sin poder editarse ni borrarse a propósito, porque son parte del registro clínico. |
| **Qué revisé o corregí yo** | Pedí cerrar todos los huecos y no subir nada sin que las verificaciones pasaran. 
| **Archivos** | `vacunacion/*`, `agenda/*`, `templates/vacunacion/*`, `templates/agenda/profesional_lista.html`, `core/test_crud_completo.py`. |

---

## 4. Ayuda con el despliegue en AWS

| Campo | Detalle |
|---|---|
| **N° / Fecha** | 4 / 27/10/2026 (el día en que lo desplegué) |
| **Herramienta** | Claude Code (archivos y guía). Claude chat, si lo usé al desplegar |
| **Para qué** | Dejar listo y explicado el despliegue en EC2 (Ubuntu 24.04): PostgreSQL, Gunicorn, Nginx con HTTPS en `codelab-catalina.duckdns.org` (IP `54.152.231.63`), tarea diaria de recordatorios y grupo de seguridad. |
| **Qué le pedí** | Parte del prompt principal (entrada 2): que Nginx envíe `X-Forwarded-Proto` con `include proxy_params`, las variables `DETRAS_DE_PROXY_HTTPS` y `CSRF_TRUSTED_ORIGINS`, y que el README explique el despliegue y que Nginx no muestre los archivos privados.|
| **Qué salió** | Los archivos `deploy/nginx-petcare.conf`, `deploy/gunicorn-petcare.service`, `deploy/cron-recordatorios`, `deploy/env.produccion.ejemplo` y la sección 10 del README (pasos, puertos del grupo de seguridad y tabla de problemas comunes). Una prueba automática confirma que `check --deploy` queda sin advertencias con las variables de producción. 

---

## Reflexión

>

**Lo que aprendí**

1. **Las reglas importantes conviene cuidarlas en dos lugares.** El código puede avisar con un mensaje claro, pero solo la base de datos asegura la regla cuando dos personas actúan al mismo tiempo. Por eso las citas no se pueden pisar ni con el código ni con PostgreSQL.
2. **La lógica va en `servicios.py` y no en las pantallas.** Así la web, la API, el Admin y los datos de ejemplo usan la misma regla y nadie se la puede saltar entrando por otro lado.
3. **Proteger datos clínicos es más que pedir login.** Hay que cuidar cada dato (un tutor no ve lo de otro), los archivos (no deben estar en una carpeta pública) y el servidor (Nginx no debe mostrarlos).
4. **Probar de verdad encuentra lo que uno no ve.** Varios errores (archivos privados, permisos del administrador, el calendario sin idioma) solo aparecieron al probar o al revisar.
5. **Las claves no van en el código.** Se guardan en el archivo `.env`, y hay que recordar que una variable vacía no usa el valor por defecto.

**Cómo usé la IA y en qué me fijé**

- La usé como una ayuda para ir más rápido, no para que pensara por mí. Yo expliqué el problema, revisé el plan antes de que se escribiera código, tomé las decisiones de diseño (entrada 3.1) y decidí cuándo se sube algo al repositorio.
- Exigí que todo se comprobara: pruebas automáticas, `check`, `check --deploy`, `makemigrations --check` y la validación de la documentación de la API.
- Pedí una revisión completa al final (entrada 3.7) para encontrar lo que faltaba, en vez de asumir que todo estaba bien.
- Tengo que poder explicar y defender cada parte del código; por eso preparé `GUIA_DEFENSA.md`.

**Qué haría distinto o mejoraría**

- Probar de verdad qué pasa cuando muchas personas reservan a la vez.
- Enviar los recordatorios por un canal real (correo o WhatsApp).
- Guardar quién ve cada ficha clínica y hacer copias de seguridad automáticas de la base y de los archivos privados.

---

## Anexo A — Prompt principal completo (textual)

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
