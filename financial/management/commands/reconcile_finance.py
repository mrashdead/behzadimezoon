from django.core.management.base import BaseCommand
import csv
import sys

from financial.services.reconciliation_service import ReconciliationService


class Command(BaseCommand):
    help = 'Run reconciliation and output reservations with discrepancies. Use --csv to save to file.'

    def add_arguments(self, parser):
        parser.add_argument('--csv', type=str, help='Path to output CSV file')

    def handle(self, *args, **options):
        csv_path = options.get('csv')

        problems = ReconciliationService.get_open_problem_reservations()

        if not problems:
            self.stdout.write('No discrepancies found.')
            return

        headers = ['reservation_id', 'expected_cash', 'reservation_cash', 'cash_difference', 'open_receivable', 'has_discrepancy']

        if csv_path:
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                for row in problems:
                    writer.writerow({k: row.get(k) for k in headers})
            self.stdout.write(self.style.SUCCESS(f'Wrote {len(problems)} discrepancy rows to {csv_path}'))
            return

        # Print table
        self.stdout.write('\t'.join(headers))
        for row in problems:
            self.stdout.write('\t'.join([str(row.get(h)) for h in headers]))
