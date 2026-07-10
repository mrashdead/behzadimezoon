# financial/services/damage_service.py

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from financial.services.transaction_service import TransactionService
from financial.services.reservation_financial_service import ReservationFinancialService
from financial.models import DamageRecord, Transaction, FinancialAccount, TransactionCategory
from reservations.models import Reservation


class DamageService:
    @staticmethod
    @transaction.atomic
    def record_damage(reservation, customer, damage_type, amount=None, description=None,
                      created_by=None, payment_method=None, external_reference=None,
                      account=None, category_name=None, notes=None):

        if amount is not None and amount < 0:
            raise ValidationError('مبلغ خسارت نمی‌تواند منفی باشد.')

        # Get default account and category if not provided
        if not account:
            account = FinancialAccount.objects.filter(account_type=FinancialAccount.AccountType.CASH).first()
        if not category_name:
            category_name = 'Damage Charge' # Default category name

        try:
            category = TransactionCategory.objects.get(name=category_name)
        except TransactionCategory.DoesNotExist:
            category = None

        dr = DamageRecord.objects.create(
            reservation=reservation,
            customer=customer,
            damage_type=damage_type,
            amount=amount,
            description=description or '',
            notes=notes or '',
            detected_by=created_by,
            detected_at=timezone.now(),
            collected=False,
        )

        # If an amount is provided, create a related CHARGE transaction.
        # TransactionService.create_damage_charge can obtain a default cash account if none is provided.
        if amount and amount > 0 and created_by:
            tx = TransactionService.create_damage_charge(
                reservation=reservation,
                amount=amount,
                created_by=created_by,
                account=account,
                category=category,
                payment_method=payment_method, # Could be None if just a charge
                external_reference=external_reference,
                note=f'خسارت برای رزرو #{reservation.pk}',
                notes=notes,
                transaction_date=timezone.now()
            )
            dr.related_transaction = tx
            dr.payment_reference = external_reference or tx.payment_reference # Use tx.payment_reference if available
            # collected status is set above based on payment_method presence at initial recording
            dr.save(update_fields=['related_transaction', 'payment_reference', 'collected'])

        # Update reservation financial status
        ReservationFinancialService.update_financial_status(reservation)
        reservation.save()

        return dr

    @staticmethod
    @transaction.atomic
    def record_damage_payment(damage_record, amount, created_by, account=None, category_name=None,
                              payment_method=None, external_reference=None, note=None):

        if amount is None or amount <= 0:
            raise ValidationError('مبلغ پرداخت خسارت باید مثبت باشد')

        # Get default account and category if not provided
        if not account:
            account = FinancialAccount.objects.filter(account_type=FinancialAccount.AccountType.CASH).first()
        if not category_name:
            category_name = 'Damage Payment' # Default category name

        try:
            category = TransactionCategory.objects.get(name=category_name)
        except TransactionCategory.DoesNotExist:
            category = None

        # Create a DAMAGE_PAYMENT transaction
        tx = TransactionService.create_damage_payment(
            reservation=damage_record.reservation,
            amount=amount,
            created_by=created_by,
            account=account,
            category=category,
            payment_method=payment_method,
            external_reference=external_reference,
            note=note or f'پرداخت خسارت برای رزرو #{damage_record.reservation.pk}',
            transaction_date=timezone.now(),
            related_transaction=damage_record.related_transaction # Link to original charge if exists
        )

        # Update the damage record itself
        damage_record.collected = True
        damage_record.payment_reference = external_reference or tx.payment_reference
        damage_record.related_transaction = tx # Link to the payment transaction
        damage_record.save()

        # Update reservation financial status
        ReservationFinancialService.update_financial_status(damage_record.reservation)
        damage_record.reservation.save()

        return tx
