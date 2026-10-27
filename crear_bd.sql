-- ============================================================
-- CREAR_BD.SQL / CREACIÓN DEL ROL Y LA BASE DE DATOS LOCAL
-- La contraseña NO está escrita aquí: se pasa por variable de psql.
--   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -v clave="TU_CLAVE" -f crear_bd.sql
-- Es idempotente. El rol necesita CREATEDB para que "manage.py test"
-- pueda crear la base de pruebas. La extensión btree_gist (para la
-- ExclusionConstraint de citas) la crea la migración: es "trusted"
-- desde PostgreSQL 13, así que no exige superusuario.
-- ============================================================
SELECT format('CREATE ROLE petcare LOGIN CREATEDB PASSWORD %L', :'clave')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'petcare')\gexec

SELECT format('ALTER ROLE petcare LOGIN CREATEDB PASSWORD %L', :'clave')\gexec

SELECT 'CREATE DATABASE petcare_db OWNER petcare ENCODING ''UTF8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'petcare_db')\gexec
