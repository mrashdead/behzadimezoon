Summary of changes

What already existed and kept unchanged:
- `Reservation` model with `created_by`, `updated_by`, `created_at`, `updated_at`, and core financial fields.
- Reservation state transition logic and payment guards.
- Custom `User` model in `accounts`.
- Database selection via `DB_ENGINE` in `core/settings.py`.

What was added:
- `payment_status` on `Reservation` to track payment lifecycle independent of reservation `status`.
- `is_deleted` soft-delete flag on `Reservation` and a soft-delete-aware default manager `objects` (and `all_objects`).
- `ReservationStatusLog` model to record status transitions with `changed_by` and timestamp.
- `Transaction` model in `financial` for lightweight audit records of payments, refunds, discounts, damages and manual adjustments.
- Migrations:
  - `reservations/migrations/0002_add_audit_and_soft_delete.py`
  - `financial/migrations/0001_initial.py`
- Small backup scripts and documentation in `docs/backup_restore.md` and `scripts/`.
- Example multi-environment settings templates in `core/settings_examples/`.

What was intentionally deferred or avoided:
- Changing existing primary keys: the project already uses `BigAutoField` default primary keys; no PK changes were made.
- Large normalization or redesign of financial/accounting models: a lightweight `Transaction` model was added for audit trails; a full accounting system is out of scope.
- Moving or renaming `core/settings.py`: instead example settings were added so you can adopt split settings safely.

Migration and rollout cautions
- Run migrations in a maintenance window and ensure backups exist before applying.
- Because `Reservation.objects` now excludes soft-deleted rows, long-running scripts or raw SQL that relied on previously-visible rows may behave differently; use `Reservation.all_objects` to access all rows.
- After migration, consider a one-time backfill for `payment_status` where appropriate (e.g., set to `PAID` where remaining_amount == 0).

Next steps (suggested):
- Add service methods to record `Transaction` entries when payments/refunds/damages are processed (currently the model exists; integration points are left for existing payment flows).
- Add periodic backup automation (cron/systemd) and restore tests into CI.
