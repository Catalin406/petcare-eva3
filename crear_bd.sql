-- ============================================================
-- CREAR_BD.SQL / OPCIÓN A: CON SUPERUSUARIO (postgres)
-- Crea el rol "petcare" y la base petcare_db. La contraseña NO está
-- escrita aquí: se pasa por variable de psql.
--   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -v clave="TU_CLAVE" -f crear_bd.sql
-- Sin la clave de postgres, usa la OPCIÓN B: crear_bd_con_rol_existente.sql.
-- Es idempotente. El rol necesita CREATEDB para que "manage.py test"
-- cree la base de pruebas. btree_gist (ExclusionConstraint de citas)
-- es una extensión "trusted" desde PostgreSQL 13: no exige superusuario.
-- ============================================================
SELECT format('CREATE ROLE petcare LOGIN CREATEDB PASSWORD %L', :'clave')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'petcare')\gexec

SELECT format('ALTER ROLE petcare LOGIN CREATEDB PASSWORD %L', :'clave')\gexec

SELECT 'CREATE DATABASE petcare_db OWNER petcare ENCODING ''UTF8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'petcare_db')\gexec
