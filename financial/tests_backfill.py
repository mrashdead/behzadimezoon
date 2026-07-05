from django.core.management import call_command
from django.test import TestCase

class BackfillCommandTests(TestCase):
    def test_backfill_dry_run_no_errors(self):
        # ensure command loads and runs in dry-run mode
        call_command('backfill_transactions', '--dry-run')

    def test_reconcile_command_runs(self):
        call_command('reconcile_finance')
