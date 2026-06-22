#!/usr/bin/env bash
# Simple PostgreSQL backup script (example)
set -euo pipefail

DB_HOST=${DB_HOST:-127.0.0.1}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-mydb}
DB_USER=${DB_USER:-myuser}
OUT_DIR=${OUT_DIR:-/var/backups}

TIMESTAMP=$(date +"%F-%H%M%S")
FILENAME="${DB_NAME}-${TIMESTAMP}.dump"
mkdir -p "$OUT_DIR"

pg_dump -Fc -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$OUT_DIR/$FILENAME"

echo "Backup created: $OUT_DIR/$FILENAME"
