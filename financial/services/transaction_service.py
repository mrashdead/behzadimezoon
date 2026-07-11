from django.db import transaction
from django.db.models import Sum, Case, When, Value, BigIntegerField
from django.utils import timezone

from financial.models import Transaction, FinancialAccount, TransactionCategory
from reservations.constants import ReservationStatus


class TransactionService:
    @staticmethod
    @transaction.atomic
    def create_transaction(
        transaction_type,
        amount,
        created_by,
        reservation=None,
        account=None,
        category=None,
        payment_method=None,
        payment_reference=None,
        description=None,
        notes=None,
        related_transaction=None,
        transaction_date=None,
        external_reference=None,
        note=None,
        transaction_status=None,
    ):
        return TransactionService.create(
            reservation=reservation,
            transaction_type=transaction_type,
            amount=amount,
            created_by=created_by,
            account=account,
            category=category,
            payment_method=payment_method,
            payment_reference=payment_reference,
            description=description,
            notes=notes,
            related_transaction=related_transaction,
            transaction_date=transaction_date,
            external_reference=external_reference,
            note=note,
            transaction_status=transaction_status,
        )

    @staticmethod
    @transaction.atomic
    def create(
        reservation,
        transaction_type,
        amount,
        created_by,
        account=None, # New: FinancialAccount for double-entry
        category=None, # New: TransactionCategory
        payment_method=None,
        payment_reference=None, # Renamed from external_reference
        description=None, # Renamed from note
        notes=None, # New: separate notes field
        related_transaction=None,
        transaction_date=None,
        external_reference=None,
        note=None,
        transaction_status=None,
    ):
        if amount is None or amount < 0:
            raise ValueError("مبلغ تراکنش باید عددی صفر یا مثبت باشد.")

        if not account:
            account, created = FinancialAccount.objects.get_or_create(
                code='CASH_DEFAULT',
                defaults={
                    'name': 'Default Cash Account',
                    'account_type': FinancialAccount.AccountType.CASH,
                    'balance': 0,
                    'description': 'Default cash account created automatically.',
                    'is_active': True,
                }
            )

        transaction_date = transaction_date or timezone.now()
        payment_reference = payment_reference or external_reference or ''
        description = description or note or ''
        notes = notes or note or ''

        tx = Transaction.objects.create(
            reservation=reservation,
            transaction_type=transaction_type,
            transaction_status=transaction_status or Transaction.TransactionStatus.POSTED, # New: Assume posted on creation via service
            amount=amount,
            transaction_date=transaction_date,
            payment_method=payment_method,
            payment_reference=payment_reference,
            description=description,
            notes=notes,
            related_transaction=related_transaction,
            created_by=created_by,
            customer=reservation.customer if reservation else None, # Auto-populate customer
            account=account,
            category=category,
        )

        # Update account balance (simplified for now, actual double-entry logic would be more complex)
        if tx.transaction_status == Transaction.TransactionStatus.POSTED:
            if tx.is_income:
                account.balance += amount
            else:
                account.balance -= amount
            account.save()

        return tx

    @staticmethod
    @transaction.atomic
    def create_deposit(reservation, amount, created_by, account=None, category=None, payment_method=None, external_reference=None, note=None, transaction_date=None):
        # For backward compatibility, map old fields to new ones
        return TransactionService.create(
            reservation=reservation,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=amount,
            created_by=created_by,
            account=account,
            category=category,
            payment_method=payment_method,
            payment_reference=external_reference, # Map old external_reference
            description=note, # Map old note
            notes=note, # Also map to new notes
            transaction_date=transaction_date,
        )

    @staticmethod
    @transaction.atomic
    def create_final_payment(reservation, amount, created_by, account=None, category=None, payment_method=None, external_reference=None, note=None, transaction_date=None):
        return TransactionService.create(
            reservation=reservation,
            transaction_type=Transaction.TransactionType.FINAL_PAYMENT,
            amount=amount,
            created_by=created_by,
            account=account,
            category=category,
            payment_method=payment_method,
            payment_reference=external_reference,
            description=note,
            notes=note,
            transaction_date=transaction_date,
        )

    @staticmethod
    @transaction.atomic
    def create_refund(reservation, amount, created_by, account=None, category=None, payment_method=None, external_reference=None, note=None, related_transaction=None, transaction_date=None):
        return TransactionService.create(
            reservation=reservation,
            transaction_type=Transaction.TransactionType.REFUND,
            amount=amount,
            created_by=created_by,
            account=account,
            category=category,
            payment_method=payment_method,
            payment_reference=external_reference,
            description=note,
            notes=note,
            related_transaction=related_transaction,
            transaction_date=transaction_date,
        )

    @staticmethod
    @transaction.atomic
    def create_damage_charge(reservation, amount, created_by, account=None, category=None, payment_method=None, external_reference=None, note=None, notes=None, related_transaction=None, transaction_date=None):
        return TransactionService.create(
            reservation=reservation,
            transaction_type=Transaction.TransactionType.DAMAGE_CHARGE,
            amount=amount,
            created_by=created_by,
            account=account,
            category=category,
            payment_method=payment_method,
            payment_reference=external_reference,
            description=note,
            notes=notes or note,
            related_transaction=related_transaction,
            transaction_date=transaction_date,
        )

    @staticmethod
    @transaction.atomic
    def create_damage_payment(reservation, amount, created_by, account=None, category=None, payment_method=None, external_reference=None, note=None, notes=None, related_transaction=None, transaction_date=None):
        return TransactionService.create(
            reservation=reservation,
            transaction_type=Transaction.TransactionType.DAMAGE_PAYMENT,
            amount=amount,
            created_by=created_by,
            account=account,
            category=category,
            payment_method=payment_method,
            payment_reference=external_reference,
            description=note,
            notes=notes or note,
            related_transaction=related_transaction,
            transaction_date=transaction_date,
        )

    @staticmethod
    @transaction.atomic
    def create_cancellation_fee(reservation, amount, created_by, account=None, category=None, note=None, transaction_date=None):
        return TransactionService.create(
            reservation=reservation,
            transaction_type=Transaction.TransactionType.CANCELLATION_FEE,
            amount=amount,
            created_by=created_by,
            account=account,
            category=category,
            description=note,
            notes=note,
            transaction_date=transaction_date,
        )

    @staticmethod
    def aggregate_reservation_totals(reservation):
        # Use the new transaction types and signed_amount for accurate aggregation
        transactions = Transaction.objects.for_reservation(reservation).filter(
            transaction_status=Transaction.TransactionStatus.POSTED,
            is_voided=False
        )

        totals = {
            'total_deposit': 0,
            'total_final_payment': 0,
            'total_damage_payment': 0,
            'total_refund': 0,
            'total_damage_charge': 0,
            'total_discount': 0,
            'total_cancellation_fee': 0,
            'total_penalty_income': 0,
            'total_adjustment': 0,
            'total_payment': 0,
        }

        for tx in transactions:
            if tx.transaction_type == Transaction.TransactionType.DEPOSIT:
                totals['total_deposit'] += tx.amount
            elif tx.transaction_type == Transaction.TransactionType.FINAL_PAYMENT:
                totals['total_final_payment'] += tx.amount
            elif tx.transaction_type == Transaction.TransactionType.PARTIAL_PAYMENT:
                totals['total_final_payment'] += tx.amount # Accumulate partials here for legacy compatibility
            elif tx.transaction_type == Transaction.TransactionType.DAMAGE_PAYMENT:
                totals['total_damage_payment'] += tx.amount
            elif tx.transaction_type == Transaction.TransactionType.PENALTY_INCOME:
                totals['total_penalty_income'] += tx.amount
            elif tx.transaction_type == Transaction.TransactionType.REFUND:
                totals['total_refund'] += tx.amount
            elif tx.transaction_type == Transaction.TransactionType.DAMAGE_CHARGE:
                totals['total_damage_charge'] += tx.amount
            elif tx.transaction_type == Transaction.TransactionType.DISCOUNT:
                totals['total_discount'] += tx.amount
            elif tx.transaction_type == Transaction.TransactionType.CANCELLATION_FEE:
                totals['total_cancellation_fee'] += tx.amount
            elif tx.transaction_type in [Transaction.TransactionType.ADJUSTMENT, Transaction.TransactionType.ADJUSTMENT_IN, Transaction.TransactionType.ADJUSTMENT_OUT]:
                # For adjustments, sum their signed amounts
                totals['total_adjustment'] += tx.signed_amount
            elif tx.transaction_type == Transaction.TransactionType.PAYMENT:
                totals['total_payment'] += tx.amount

        return totals

    @staticmethod
    def reservation_cash_inflow(reservation):
        # Sum all positive cash flow transaction types
        inflows = Transaction.objects.for_reservation(reservation).cash_in().aggregate(total=Sum('amount'))['total'] or 0
        outflows = Transaction.objects.for_reservation(reservation).cash_out().aggregate(total=Sum('amount'))['total'] or 0
        return inflows - outflows

    @staticmethod
    def reservation_accrual_revenue(reservation):
        # This needs to be carefully redefined based on the new model structure.
        # For now, it will be a simplified version using new transaction types.
        # Assuming final_price is the base revenue.
        gross_revenue = reservation.final_price or 0

        # Deduct discounts recorded as transactions
        discounts_tx = Transaction.objects.for_reservation(reservation).filter(
            transaction_type=Transaction.TransactionType.DISCOUNT,
            transaction_status=Transaction.TransactionStatus.POSTED
        ).aggregate(total=Sum('amount'))['total'] or 0

        # Add cancellation fees and damage charges if they are part of accrual revenue
        cancellation_fees_tx = Transaction.objects.for_reservation(reservation).filter(
            transaction_type=Transaction.TransactionType.CANCELLATION_FEE,
            transaction_status=Transaction.TransactionStatus.POSTED
        ).aggregate(total=Sum('amount'))['total'] or 0

        damage_charges_tx = Transaction.objects.for_reservation(reservation).filter(
            transaction_type=Transaction.TransactionType.DAMAGE_CHARGE,
            transaction_status=Transaction.TransactionStatus.POSTED
        ).aggregate(total=Sum('amount'))['total'] or 0

        return gross_revenue - discounts_tx + cancellation_fees_tx + damage_charges_tx


    @staticmethod
    def reservation_open_receivable(reservation):
        # This needs to be carefully redefined based on the new model structure.
        # For now, it will be a simplified version.
        total_charged = (Transaction.objects.for_reservation(reservation).filter(
            transaction_type__in=[Transaction.TransactionType.DAMAGE_CHARGE, Transaction.TransactionType.CANCELLATION_FEE],
            transaction_status=Transaction.TransactionStatus.POSTED
        ).aggregate(total=Sum('amount'))['total'] or 0)

        total_paid_for_receivables = (Transaction.objects.for_reservation(reservation).filter(
            transaction_type=Transaction.TransactionType.DAMAGE_PAYMENT,
            transaction_status=Transaction.TransactionStatus.POSTED
        ).aggregate(total=Sum('amount'))['total'] or 0)

        # Also consider the reservation's remaining_amount as a receivable
        reservation_remaining = reservation.remaining_amount or 0

        return max(0, total_charged - total_paid_for_receivables + reservation_remaining)

    @staticmethod
    def get_total_inflow():
        return Transaction.objects.filter(
            transaction_status=Transaction.TransactionStatus.POSTED,
            is_voided=False,
            transaction_type__in=[
                Transaction.TransactionType.DEPOSIT,
                Transaction.TransactionType.FINAL_PAYMENT,
                Transaction.TransactionType.PARTIAL_PAYMENT,
                Transaction.TransactionType.DAMAGE_PAYMENT,
                Transaction.TransactionType.PENALTY_INCOME,
                Transaction.TransactionType.TRANSFER_IN,
                Transaction.TransactionType.ADJUSTMENT_IN,
            ],
        ).aggregate(total=Sum('amount'))['total'] or 0

    @staticmethod
    def get_total_outflow():
        return Transaction.objects.filter(
            transaction_status=Transaction.TransactionStatus.POSTED,
            is_voided=False,
            transaction_type__in=[
                Transaction.TransactionType.REFUND,
                Transaction.TransactionType.TRANSFER_OUT,
                Transaction.TransactionType.LAUNDRY_EXPENSE,
                Transaction.TransactionType.REPAIR_EXPENSE,
                Transaction.TransactionType.SUPPLY_EXPENSE,
                Transaction.TransactionType.UTILITY_EXPENSE,
                Transaction.TransactionType.STAFF_SALARY,
                Transaction.TransactionType.RENT_EXPENSE,
                Transaction.TransactionType.MARKETING_EXPENSE,
            ],
        ).aggregate(total=Sum('amount'))['total'] or 0

    @staticmethod
    def get_total_net_financial():
        return TransactionService.get_total_inflow() - TransactionService.get_total_outflow()
