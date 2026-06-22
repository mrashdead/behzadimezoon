#!/usr/bin/env bash
# Simple PostgreSQL restore script (example)
set -euo pipefail

DB_HOST=${DB_HOST:-127.0.0.1}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-restore_db}
DB_USER=${DB_USER:-myuser}
DUMP_FILE=${1:-}

if [ -z "$DUMP_FILE" ]; then
  echo "Usage: $0 /path/to/dump.dump"
  exit 2
fi

pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" --no-owner --no-privileges "$DUMP_FILE"

echo "Restore finished into $DB_NAME"
