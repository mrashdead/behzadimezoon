from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from reservations.models import Reservation
from financial.models import Transaction
from django.db import connection


class Command(BaseCommand):
    help = 'Backfill Transaction rows from existing Reservation financial fields. Use --dry-run to preview changes.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would be created without saving')
        parser.add_argument('--limit', type=int, default=0, help='Limit number of reservations processed (0 = all)')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit'] or None

        # Ensure required reservation snapshot columns exist in DB (migrations applied)
        table_name = Reservation._meta.db_table
        required_cols = {'dress_daily_price_snapshot', 'financial_snapshot', 'total_cash_collected_snapshot'}
        with connection.cursor() as cursor:
            existing = {col.name for col in connection.introspection.get_table_description(cursor, table_name)}

        missing = required_cols - existing
        if missing:
            raise CommandError(
                'Missing reservation snapshot columns in DB: %s. Run migrations before backfill.' % (', '.join(sorted(missing)))
            )

        qs = Reservation.all_objects.all().order_by('id')
        if limit:
            qs = qs[:limit]

        created_total = 0
        skipped_with_transactions = 0

        for res in qs:
            # skip soft-deleted or archived? keep for audit; process all
            existing_tx_count = getattr(res, 'transactions', None)
            if existing_tx_count is not None and res.transactions.exists():
                skipped_with_transactions += 1
                continue

            # prepare inferred transactions list
            to_create = []

            # deposit
            deposit = res.deposit_amount or 0
            if deposit > 0:
                to_create.append({
                    'type': Transaction.Type.DEPOSIT,
                    'amount': deposit,
                    'payment_method': getattr(res, 'payment_method', None),
                    'external_reference': getattr(res, 'payment_tracking_code', None),
                    'transaction_date': getattr(res, 'created_at', timezone.now()),
                })

            # remaining/final payment
            remaining = res.remaining_payment_amount or 0
            if remaining > 0:
                to_create.append({
                    'type': Transaction.Type.FINAL_PAYMENT,
                    'amount': remaining,
                    'payment_method': getattr(res, 'remaining_payment_method', None) or getattr(res, 'payment_method', None),
                    'external_reference': getattr(res, 'remaining_payment_tracking_code', None) or getattr(res, 'payment_tracking_code', None),
                    'transaction_date': getattr(res, 'remaining_paid_at', getattr(res, 'updated_at', timezone.now())),
                })

            # refunded
            refunded = res.refunded_amount or 0
            if refunded > 0:
                to_create.append({
                    'type': Transaction.Type.REFUND,
                    'amount': refunded,
                    'payment_method': getattr(res, 'payment_method', None),
                    'external_reference': None,
                    'transaction_date': getattr(res, 'cancelled_at', getattr(res, 'updated_at', timezone.now())),
                })

            # damage charge
            damage = res.damage_amount or 0
            if damage > 0:
                # if there are explicit DamageRecord objects, skip creating a generic charge here
                if not getattr(res, 'damage_records', None) or not res.damage_records.exists():
                    to_create.append({
                        'type': Transaction.Type.DAMAGE_CHARGE,
                        'amount': damage,
                        'payment_method': None,
                        'external_reference': None,
                        'transaction_date': getattr(res, 'updated_at', timezone.now()),
                    })

            if not to_create:
                continue

            self.stdout.write(self.style.NOTICE(f"Reservation #{res.id}: will create {len(to_create)} inferred transactions (dry_run={dry_run})"))

            if dry_run:
                for t in to_create:
                    self.stdout.write(f"  - {t['type']} {t['amount']} via {t.get('payment_method')} on {t['transaction_date']}")
                continue

            # create within atomic block
            with transaction.atomic():
                for t in to_create:
                    tx = Transaction(
                        reservation=res,
                        customer=res.customer,
                        type=t['type'],
                        amount=t['amount'],
                        payment_method=t.get('payment_method'),
                        external_reference=t.get('external_reference'),
                        transaction_date=t.get('transaction_date') or timezone.now(),
                        reservation_snapshot=res.get_payment_snapshot_for_audit(),
                        created_by=getattr(res, 'created_by'),
                        posting_status=Transaction.PostingStatus.POSTED,
                        is_immutable=True,
                        note='Backfilled from Reservation fields (inferred).'
                    )
                    tx.save()
                    created_total += 1

        self.stdout.write(self.style.SUCCESS(f"Backfill complete. Created: {created_total}. Skipped reservations with existing transactions: {skipped_with_transactions}"))
