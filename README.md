# 🐾 PetCare — Sistema de Gestión de Citas y Fichas Médicas para Veterinaria

Proyecto de la **Evaluación 3 (individual)** de *Desarrollo Backend* — INACAP.
**Autora:** Catalina Quezada Sanzana · **Proyecto 1:** Sistema de Gestión de Citas y Fichas Médicas para Veterinaria.

| | |
|---|---|
| **Sitio en producción** | <https://codelab-catalina.duckdns.org> |
| **IP pública (AWS EC2)** | `54.152.231.63` |
| **Documentación de la API (Swagger)** | <https://codelab-catalina.duckdns.org/api/docs/> (exige iniciar sesión en el sitio, cualquier rol) |
| **Django Admin** | <https://codelab-catalina.duckdns.org/admin/> |
| **Repositorio** | <https://github.com/Catalin406/petcare-eva3> |

---

## 1. ¿Qué problema resuelve?

Una clínica veterinaria tenía tres dolores:

| Problema | Cómo lo resuelve PetCare |
|---|---|
| **Citas que se solapan** | Agenda por profesional con disponibilidad semanal. Un horario ocupado no se puede volver a reservar: lo valida el servicio (mensaje claro) **y** una `ExclusionConstraint` de PostgreSQL (`tstzrange` + `btree_gist`) que lo impide aunque dos personas reserven al mismo tiempo. |
| **Fichas clínicas en papel que se pierden** | Ficha clínica digital por mascota (se crea sola), con atenciones, recetas y exámenes adjuntos, vista como línea de tiempo. Las atenciones **no se borran**. |
| **Falta de seguimiento de vacunas** | Catálogo de vacunas con periodicidad; la próxima dosis se calcula sola; el comando `generar_recordatorios` avisa por correo al tutor y marca lo vencido. |

## 2. Stack

| Capa | Tecnología |
|---|---|
| Lenguaje | Python 3.12 |
| Framework | Django 5.2 LTS |
| API | Django REST Framework · SimpleJWT (JWT) · drf-spectacular (Swagger/OpenAPI) · django-filter |
| Base de datos | **PostgreSQL** (psycopg 3). No se usa SQLite. |
| Configuración | python-decouple + archivo `.env` |
| Front | Plantillas Django · Bootstrap 5.3 + Bootstrap Icons · FullCalendar 6 |
| Servidor | Nginx (HTTPS con Let's Encrypt) → Gunicorn → Django, en Ubuntu 24.04 sobre AWS EC2 |
| Zona horaria / idioma | `America/Santiago` · `es-cl` |

## 3. Roles y permisos

| Rol | Puede |
|---|---|
| **Administrador** | Todo, incluido el Django Admin. Solo lee las atenciones clínicas (no las escribe). |
| **Recepcionista** | Gestiona tutores, mascotas y citas. Programa controles. **No** ve ni edita fichas clínicas, atenciones ni exámenes. |
| **Veterinario** | Ve su agenda, confirma citas, define su disponibilidad y bloqueos, **escribe** atenciones/recetas/exámenes, edita la ficha y registra vacunas. |
| **Tutor** | Solo ve **sus** mascotas, citas, fichas (solo lectura) y recordatorios. Solicita y cancela citas propias con la anticipación mínima configurable. |

El control es **por rol** (vistas y API) y **por objeto**: un tutor jamás ve datos de otro tutor (lo ajeno responde 404). La matriz completa rol × ruta está comprobada por pruebas (`core/test_matriz_roles.py`).

## 4. Ejecución en local (Windows / PowerShell)

Requisitos: Python 3.12, PostgreSQL 13 o superior y Git.

```powershell
git clone https://github.com/Catalin406/petcare-eva3.git
cd petcare-eva3

# 1) Entorno virtual con Python 3.12
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version            # debe decir 3.12.x
pip install -r requirements.txt

# 2) Variables de entorno
Copy-Item .env.example .env
#    Edita .env: SECRET_KEY y los DB_*
```

### 4.1 Crear la base de datos (elige UNA opción)

**Opción A — con el superusuario `postgres`** (crea el rol `petcare` y la base `petcare_db`; la clave se pasa por variable, nunca queda escrita en el repositorio):

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -v clave="TU_CLAVE" -f crear_bd.sql
# en .env:  DB_USER=petcare   DB_PASSWORD=TU_CLAVE   DB_NAME=petcare_db
```

**Opción B — sin superusuario, con un rol que tenga `CREATEDB`** (por ejemplo, el de otra asignatura):

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U TU_ROL -h localhost -d postgres -f crear_bd_con_rol_existente.sql
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U TU_ROL -h localhost -d petcare_db -c "CREATE EXTENSION IF NOT EXISTS btree_gist"
# en .env:  DB_USER=TU_ROL   DB_PASSWORD=la clave de ese rol   DB_NAME=petcare_db
```

> `btree_gist` es una extensión *trusted* desde PostgreSQL 13: el **dueño de la base** puede crearla sin ser superusuario. La migración de `agenda` también la crea (`BtreeGistExtension`). El rol necesita `CREATEDB` para que `manage.py test` pueda crear su base temporal.

### 4.2 Migrar, cargar datos y levantar

```powershell
python manage.py migrate
python manage.py seed_data          # datos de demostración + imprime las credenciales
python manage.py runserver          # http://127.0.0.1:8000/
```

Los **correos** de los recordatorios se imprimen en la consola del servidor (backend de consola por defecto). Para ver el efecto: `python manage.py generar_recordatorios`.

## 5. Variables de entorno

Todo lo sensible o dependiente del entorno se configura en `.env` (nunca en el código). Plantilla: [`.env.example`](.env.example).

> ⚠️ **Trampa de python-decouple:** una variable *presente pero vacía* (`VAR=`) vale `""` y **no** cae al valor por defecto. Si quieres el default, **borra o comenta la línea**.

| Variable | Obligatoria | Por defecto | Descripción |
|---|---|---|---|
| `SECRET_KEY` | ✅ | — | Clave secreta de Django. Sin ella el proyecto no arranca. |
| `DEBUG` | | `False` | `True` solo en local. |
| `ALLOWED_HOSTS` | | `localhost,127.0.0.1` | Lista separada por comas. |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | ✅ | — | Conexión a PostgreSQL. |
| `DB_HOST` / `DB_PORT` | | `localhost` / `5432` | |
| `CSRF_TRUSTED_ORIGINS` | | vacío | Orígenes https aceptados en POST (servidor). |
| `DETRAS_DE_PROXY_HTTPS` | | `False` | `True` en el servidor: confía en `X-Forwarded-Proto`, redirige a https, cookies seguras y HSTS. |
| `COOKIES_SEGURAS` | | = `DETRAS_DE_PROXY_HTTPS` | Fuerza cookies `Secure` aunque no haya proxy. |
| `HSTS_SEGUNDOS` | | `3600` | Duración de HSTS (solo con proxy). |
| `SESSION_EXPIRA_SEGUNDOS` | | `1800` | Vida de la sesión por inactividad (30 min). |
| `CITA_ANTICIPACION_MIN_HORAS` | | `24` | Anticipación mínima para que un **tutor** pida o cancele una cita. |
| `DIAS_ANTICIPACION_RECORDATORIO` | | `30` | Ventana de `generar_recordatorios`. |
| `EMAIL_BACKEND` / `EMAIL_DESDE` | | consola / `PetCare <no-responder@petcare.local>` | Correo de los recordatorios. |
| `ALUMNO_NOMBRE` | | `Catalina Quezada Sanzana` | Aparece en el footer y en Swagger. |

## 6. Pruebas

```powershell
python manage.py test                    # todas (310 pruebas, ~1 min)
python manage.py test agenda             # una app
python manage.py check
python manage.py check --deploy          # con las variables de producción (ver deploy/env.produccion.ejemplo)
python manage.py makemigrations --check  # migraciones al día
python manage.py spectacular --validate --fail-on-warn --file schema.yml
```

Qué cubren las pruebas: solapamiento por profesional y por mascota (servicio **y** constraint de PostgreSQL), cita fuera de disponibilidad / en el pasado / en un bloqueo, transiciones de estado, atención → cita `ATENDIDA` en la misma transacción, próxima dosis, `generar_recordatorios` idempotente, validación de RUT, permisos por rol y por objeto (web y API), login obligatorio en toda la web, archivos privados (403/404), CSRF, sesiones, contraseñas, `check --deploy`, Django Admin completo y el `seed_data` idempotente.

## 7. Estructura del proyecto

```
config/        settings, urls, api_urls (router DRF), wsgi
core/          validadores (RUT, archivos), archivos privados, permisos DRF, middleware de login,
               mixins de rol, resumen de inicio, seed_data, fábricas de prueba
usuarios/      Usuario con rol (is_staff sincronizado), login/logout, JWT con rol
clientes/      Tutor y Mascota (CRUD web + API, servicios.py)
agenda/        Profesional, DisponibilidadSemanal, BloqueoAgenda, Cita, HistorialCita,
               servicios.py (reglas), calendario FullCalendar
clinica/       FichaClinica, Atencion, Receta, Examen (línea de tiempo, adjuntos privados)
vacunacion/    Vacuna, RegistroVacuna, ControlPeriodico, Recordatorio, comando generar_recordatorios
templates/     base, navbar por rol, 403/404/500, admin/ (marca PetCare)
static/        css/tema.css, admin/css/petcare_admin.css, js/ (calendario, formulario de cita)
deploy/        nginx, gunicorn (systemd), cron y .env de producción de ejemplo
```

La lógica de negocio vive en cada `servicios.py`; las vistas web, la API, el Admin y el seed solo los llaman.

## 8. Rutas principales

**Web** (todas exigen login): `/` · `/login/` · `/logout/` (POST) · `/tutores/` · `/mascotas/` · `/agenda/calendario/` · `/agenda/citas/` · `/agenda/disponibilidad/` · `/clinica/fichas/<mascota>/` · `/clinica/atenciones/nueva/` · `/recordatorios/` · `/vacunacion/{catalogo,aplicadas,controles}/` · `/admin/`

**API** (JWT o sesión): `POST /api/auth/token/` · `POST /api/auth/token/refresh/` · `/api/tutores/` · `/api/mascotas/` (+ `/{id}/foto/`) · `/api/profesionales/` (+ `/{id}/horarios/?fecha=`) · `/api/disponibilidades/` · `/api/bloqueos/` · `/api/citas/` (+ `cambiar-estado`, `cancelar`, `historial`) · `/api/agenda/eventos/` · `/api/fichas/` · `/api/atenciones/` · `/api/recetas/` · `/api/examenes/` (+ `/{id}/archivo/`) · `/api/vacunas/` · `/api/registros-vacuna/` · `/api/controles/` · `/api/recordatorios/` (+ `panel`, `generar`) · Swagger en `/api/docs/` y esquema en `/api/schema/` (ambos exigen sesión iniciada)

## 9. Credenciales de demostración

Se crean con `python manage.py seed_data` (también en el servidor). *Son solo para evaluación.*

| Rol | Usuario | Contraseña |
|---|---|---|
| Administrador | `admin` | `Admin#2026Pet` |
| Recepcionista | `recepcion` | `Recep#2026Pet` |
| Veterinaria | `dra.munoz` | `Vet#2026Pet` |
| Veterinario | `dr.fuentes` | `Vet#2026Pet` |
| Tutora | `carolina.rojas` | `Tutor#2026Pet` |
| Tutor | `felipe.araya` | `Tutor#2026Pet` |
| Tutora | `daniela.soto` | `Tutor#2026Pet` |

## 10. Despliegue en AWS EC2 (Ubuntu 24.04 + Nginx + Gunicorn + PostgreSQL)

Datos del servidor: IP pública **54.152.231.63** · dominio **codelab-catalina.duckdns.org** (DuckDNS apunta a esa IP). Los archivos de ejemplo están en [`deploy/`](deploy/).

### 10.1 Grupo de seguridad (AWS)

| Puerto | Origen | Para qué |
|---|---|---|
| 22 (SSH) | Tu IP | Administrar el servidor |
| 80 (HTTP) | 0.0.0.0/0 | Redirección a https y desafío de Let's Encrypt |
| 443 (HTTPS) | 0.0.0.0/0 | El sitio |
| 5432 (PostgreSQL) | **cerrado** | La base solo se usa desde el propio servidor |
| 8000 (Gunicorn) | **cerrado** | Gunicorn escucha solo en `127.0.0.1` |

### 10.2 Paquetes y base de datos

```bash
sudo apt update && sudo apt install -y python3.12-venv python3-pip nginx postgresql postgresql-contrib git certbot python3-certbot-nginx

sudo -u postgres psql <<'SQL'
CREATE ROLE petcare LOGIN CREATEDB PASSWORD 'UNA-CLAVE-DISTINTA-A-LA-LOCAL';
CREATE DATABASE petcare_db OWNER petcare ENCODING 'UTF8' TEMPLATE template0;
\c petcare_db
CREATE EXTENSION IF NOT EXISTS btree_gist;
SQL
```

### 10.3 Código, entorno y datos

```bash
cd ~ && git clone https://github.com/Catalin406/petcare-eva3.git && cd petcare-eva3
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp deploy/env.produccion.ejemplo .env && nano .env      # SECRET_KEY, DB_PASSWORD, etc.
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py seed_data                                # datos y credenciales de demostración
python manage.py check --deploy                           # debe terminar sin advertencias
mkdir -p archivos_privados && chmod 750 archivos_privados
```

Variables del `.env` del servidor: `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS=codelab-catalina.duckdns.org,54.152.231.63,localhost,127.0.0.1` (los dos últimos sirven para probar con `curl` desde el propio servidor), `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST=localhost`, `DB_PORT=5432`, `CSRF_TRUSTED_ORIGINS=https://codelab-catalina.duckdns.org`, `DETRAS_DE_PROXY_HTTPS=True`, `ALUMNO_NOMBRE`.

### 10.4 Gunicorn como servicio

```bash
sudo cp deploy/gunicorn-petcare.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now gunicorn-petcare
sudo systemctl status gunicorn-petcare        # debe decir "active (running)"
```

### 10.5 Nginx + HTTPS

```bash
sudo cp deploy/nginx-petcare.conf /etc/nginx/sites-available/petcare
sudo ln -s /etc/nginx/sites-available/petcare /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo certbot --nginx -d codelab-catalina.duckdns.org    # emite el certificado Let's Encrypt
sudo nginx -t && sudo systemctl reload nginx
```

`include proxy_params;` (ya en el archivo) hace que Nginx envíe `X-Forwarded-Proto`; con `DETRAS_DE_PROXY_HTTPS=True` Django lo respeta (`SECURE_PROXY_SSL_HEADER`), redirige a https y marca las cookies como seguras.

### 10.6 Recordatorios diarios

```bash
crontab -e      # pegar la línea de deploy/cron-recordatorios
```

### 10.7 ⚠️ Archivos privados: Nginx NO debe exponer esa carpeta

Las **fotos de mascotas** y los **adjuntos de exámenes** son datos clínicos. Se guardan en `archivos_privados/` (fuera de `static/`, sin `MEDIA_URL`) y Django los entrega **solo** por vistas con login y permisos (`/mascotas/<id>/foto/`, `/clinica/examenes/<id>/archivo/` y sus equivalentes en la API). En Nginx **no debe existir** ningún `location` / `alias` / `root` que apunte a `archivos_privados/` ni a `/media/` (el archivo de ejemplo los bloquea con `return 404`). Verificación rápida: `curl -I https://codelab-catalina.duckdns.org/media/mascotas/x.png` → 404 y, sin sesión, `/mascotas/1/foto/` → redirección al login.

### 10.8 Actualizar el sitio

```bash
cd ~/petcare-eva3 && git pull && source .venv/bin/activate
pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput
sudo systemctl restart gunicorn-petcare
```

### 10.9 Si algo falla

| Síntoma | Revisar |
|---|---|
| 502 Bad Gateway | `sudo systemctl status gunicorn-petcare` y `journalctl -u gunicorn-petcare -n 50` |
| 400 Bad Request | Falta el dominio/IP en `ALLOWED_HOSTS` |
| 403 CSRF al iniciar sesión | `CSRF_TRUSTED_ORIGINS` (con `https://`) y `include proxy_params` en Nginx |
| Bucle de redirecciones | `DETRAS_DE_PROXY_HTTPS=True` sin `X-Forwarded-Proto` en Nginx |
| CSS sin estilos | Falta `collectstatic` o el `alias /static/` apunta a otra ruta |
| `permission denied` al subir un examen | La carpeta `archivos_privados/` debe pertenecer al usuario de Gunicorn |

## 11. Reglas de negocio destacadas

- **Cita:** no en el pasado · completa dentro de una franja del profesional · fuera de bloqueos · sin solape con otra cita activa del profesional **ni** de la misma mascota. `ATENDIDA` y `NO_ASISTIO` siguen ocupando el horario; solo `CANCELADA` lo libera.
- **Estados:** `PROGRAMADA → CONFIRMADA / ATENDIDA / CANCELADA / NO_ASISTIO`; `CONFIRMADA → ATENDIDA / CANCELADA / NO_ASISTIO`; los demás son finales. Cada cambio queda en el historial.
- **Atención:** se registra desde una cita `PROGRAMADA` o `CONFIRMADA` (que pasa a `ATENDIDA` en la misma transacción) o sin cita (urgencia). Solo el veterinario la escribe; nadie la borra.
- **Mascota:** con historial no se elimina, se desactiva. **Tutor:** con mascotas no se elimina, se desactiva su cuenta.
- **Recordatorios:** `generar_recordatorios` es idempotente (restricciones únicas + `get_or_create` + `enviado_en`); una nueva aplicación de la vacuna cierra el aviso anterior.
- **Correo del tutor:** única fuente de verdad = el email de su `Usuario`.
