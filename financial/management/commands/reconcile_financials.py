from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models import Sum

from reservations.models import Reservation
from financial.models import Transaction


class Command(BaseCommand):
    help = 'Reconcile Reservation snapshots against Transaction ledger. Reports discrepancies.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0, help='Limit number of reservations processed (0 = all)')

    def handle(self, *args, **options):
        limit = options['limit'] or None

        # ensure snapshot columns exist
        table_name = Reservation._meta.db_table
        required_cols = {'financial_snapshot', 'total_cash_collected_snapshot'}
        with connection.cursor() as cursor:
            existing = {col.name for col in connection.introspection.get_table_description(cursor, table_name)}
        missing = required_cols - existing
        if missing:
            raise CommandError('Missing reservation snapshot columns in DB: %s. Run migrations.' % (', '.join(sorted(missing))))

        qs = Reservation.all_objects.all().order_by('id')
        if limit:
            qs = qs[:limit]

        mismatches = []
        for res in qs:
            # Sum posted transaction signed amounts for reservation
            tx_sum = Transaction.objects.filter(reservation=res, posting_status=Transaction.PostingStatus.POSTED).aggregate(
                total=Sum('amount')
            )['total'] or 0

            snapshot_total = getattr(res, 'total_cash_collected_snapshot', None) or res.total_received_amount()

            if tx_sum != snapshot_total:
                mismatches.append((res.id, snapshot_total, tx_sum))

        self.stdout.write(f"Processed {qs.count()} reservations; mismatches: {len(mismatches)}")
        for r_id, snap, tx in mismatches[:200]:
            self.stdout.write(f"Reservation #{r_id}: snapshot_total={snap} transaction_sum={tx}")
