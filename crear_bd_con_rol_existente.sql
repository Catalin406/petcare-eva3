-- ============================================================
-- CREAR_BD_CON_ROL_EXISTENTE.SQL / OPCIÓN B (SIN SUPERUSUARIO)
-- Para quien NO tiene la clave de "postgres" pero sí un rol propio
-- con permiso CREATEDB (p. ej. el de otra asignatura). Se conecta
-- con ese rol; la contraseña la pide psql (no se escribe aquí):
--   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U TU_ROL -h localhost -d postgres -f crear_bd_con_rol_existente.sql
-- Luego, dentro de la base creada, el dueño activa btree_gist
-- (extensión "trusted" desde PostgreSQL 13: no exige superusuario):
--   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U TU_ROL -h localhost -d petcare_db -c "CREATE EXTENSION IF NOT EXISTS btree_gist"
-- (la migración de agenda también la crea con BtreeGistExtension).
-- Después pon DB_USER=TU_ROL y su clave en el .env.
-- ============================================================
SELECT format('CREATE DATABASE petcare_db OWNER %I ENCODING ''UTF8'' TEMPLATE template0', current_user)
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'petcare_db')\gexec
