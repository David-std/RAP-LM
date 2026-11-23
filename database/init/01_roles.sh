#!/bin/sh
# Creates the separated database roles on first start of the PostGIS container.
# raplm_reader: SELECT only (API). raplm_publisher: batch publication.
# The container superuser (POSTGRES_USER) owns the schema and runs migrations.
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE ROLE raplm_reader LOGIN PASSWORD '${RAPLM_READER_PASSWORD}';
CREATE ROLE raplm_publisher LOGIN PASSWORD '${RAPLM_PUBLISHER_PASSWORD}';
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO raplm_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO raplm_publisher;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO raplm_publisher;
ALTER ROLE raplm_reader SET default_transaction_read_only = on;
SQL
