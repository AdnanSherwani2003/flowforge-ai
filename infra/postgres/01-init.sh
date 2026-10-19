#!/bin/sh
set -eu

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname postgres \
  -v ff_pass="$FLOWFORGE_DB_PASSWORD" \
  -v n8n_pass="$N8N_DB_PASSWORD" <<'SQL'
CREATE ROLE flowforge_app LOGIN PASSWORD :'ff_pass';
CREATE ROLE n8n_app LOGIN PASSWORD :'n8n_pass';

CREATE DATABASE flowforge OWNER flowforge_app;
CREATE DATABASE flowforge_n8n OWNER n8n_app;
SQL
