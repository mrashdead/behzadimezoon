from django.core.management.base import BaseCommand
from django.db import transaction

from financial.models import Transaction
from reservations.models import Reservation
from financial.services.transaction_service import TransactionService


class Command(BaseCommand):
    help = 'Backfill legacy reservation financial fields into Transaction rows (safe, idempotent).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Do not write changes; only report counts')
        parser.add_argument('--limit', type=int, help='Limit number of reservations to process')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run')
        limit = options.get('limit')

        qs = Reservation.objects.all().order_by('id')
        if limit:
            qs = qs[:limit]

        created = 0
        skipped = 0

        for reservation in qs:
            # Determine owner for created_by: prefer reservation.updated_by, then created_by.
            created_by = getattr(reservation, 'updated_by', None) or reservation.created_by

            # Defensive: if no created_by, skip and log
            if created_by is None:
                self.stdout.write(f"Skipping reservation {reservation.pk}: no user to attribute backfill to")
                skipped += 1
                continue

            # Use transaction atomic to ensure per-reservation safety
            with transaction.atomic():
                # Create DEPOSIT if deposit_amount > 0 and no existing legacy backfill DEPOSIT
                if (reservation.deposit_amount or 0) > 0:
                    existed = reservation.transactions.filter(external_reference='legacy-backfill', type=Transaction.Type.DEPOSIT).exists()
                    if not existed:
                        if not dry_run:
                            TransactionService.create_deposit(
                                reservation=reservation,
                                amount=reservation.deposit_amount,
                                created_by=created_by,
                                payment_method=reservation.payment_method,
                                external_reference='legacy-backfill',
                                note='بازسازی از deposit_amount رزرو'
                            )
                        created += 1

                # Create FINAL_PAYMENT if remaining_payment_amount > 0
                if (reservation.remaining_payment_amount or 0) > 0:
                    existed = reservation.transactions.filter(external_reference='legacy-backfill', type='FINAL_PAYMENT').exists()
                    if not existed:
                        if not dry_run:
                            TransactionService.create_final_payment(
                                reservation=reservation,
                                amount=reservation.remaining_payment_amount,
                                created_by=created_by,
                                payment_method=reservation.remaining_payment_method,
                                external_reference='legacy-backfill',
                                note='بازسازی از remaining_payment_amount رزرو'
                            )
                        created += 1

                # Create REFUND if refunded_amount > 0
                if (reservation.refunded_amount or 0) > 0:
                    existed = reservation.transactions.filter(external_reference='legacy-backfill', type='REFUND').exists()
                    if not existed:
                        if not dry_run:
                            TransactionService.create_refund(
                                reservation=reservation,
                                amount=reservation.refunded_amount,
                                created_by=created_by,
                                payment_method=reservation.payment_method,
                                external_reference='legacy-backfill',
                                note='بازسازی از refunded_amount رزرو'
                            )
                        created += 1

                # Create DISCOUNT if discount_amount > 0
                if (reservation.discount_amount or 0) > 0:
                    existed = reservation.transactions.filter(external_reference='legacy-backfill', type='DISCOUNT').exists()
                    if not existed:
                        if not dry_run:
                            TransactionService.create(
                                reservation=reservation,
                                transaction_type='DISCOUNT',
                                amount=reservation.discount_amount,
                                created_by=created_by,
                                note='بازسازی از discount_amount رزرو',
                                external_reference='legacy-backfill'
                            )
                        created += 1

                # Create DAMAGE_CHARGE if damage_amount > 0
                if (reservation.damage_amount or 0) > 0:
                    existed = reservation.transactions.filter(external_reference='legacy-backfill', type='DAMAGE_CHARGE').exists()
                    if not existed:
                        if not dry_run:
                            TransactionService.create_damage_charge(
                                reservation=reservation,
                                amount=reservation.damage_amount,
                                created_by=created_by,
                                note='بازسازی از damage_amount رزرو',
                            )
                        created += 1

        self.stdout.write(self.style.SUCCESS(f'Backfill complete. Created ~{created} transactions, skipped {skipped} reservations.'))
