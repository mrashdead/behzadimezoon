Backup and Restore - Postgres (production)

Overview
- Daily backups: use `pg_dump` to create logical dumps of the PostgreSQL database.
- Off-server storage: copy dumps to an object store (S3) or remote server via `rsync`/`scp`.
- Restore testing: periodically restore backups into a staging database to verify integrity.

Simple daily backup (example)
- Run on the DB host or a machine with network access and credentials.

Command example (bash):

pg_dump -Fc -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f /backups/$DB_NAME-$(date +"%F-%H%M%S").dump

Notes:
- Use `-Fc` (custom format) for compressed, restorable dumps with `pg_restore`.
- Protect credentials using a `.pgpass` file or environment variables; avoid embedding secrets in scripts.

Copy backups off-server (example)

# copy to remote backup host
rsync -avz /backups/ user@backup-host:/srv/db-backups/

# or upload to S3 using awscli
aws s3 cp /backups/$FILE s3://mybucket/db-backups/$FILE

Restore (test)

# create DB and user if needed, then
pg_restore -h $DB_HOST -p $DB_PORT -U $DB_USER -d $RESTORE_DB --no-owner --no-privileges /backups/file.dump

Recommendations
- Keep at least 14 days of backups with daily rotation; retain weekly/monthly snapshots longer.
- Verify restores weekly by restoring a recent backup into a staging database and running smoke tests.
- Encrypt backups at rest and in transit.
- Automate with cron or systemd timers and monitor success/failure via alerts.

Windows notes
- Use `pg_dump` from the PostgreSQL installation and copy files to a secure network share or object store.
