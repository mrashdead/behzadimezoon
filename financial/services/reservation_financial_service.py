# financial/services/reservation_financial_service.py

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.db.models import F, Sum, Case, When, Value, BigIntegerField

from financial.services.transaction_service import TransactionService
from financial.models import Transaction, FinancialAccount, TransactionCategory
from reservations.constants import PaymentMethod
from reservations.models import Reservation


class ReservationFinancialService:

    @staticmethod
    def _get_cash_account():
        """Returns the default cash account, or raises an error if not found."""
        account = FinancialAccount.objects.filter(account_type=FinancialAccount.AccountType.CASH).first()
        if not account:
            raise FinancialAccount.DoesNotExist("حساب پیش‌فرض نقدی (CASH) یافت نشد. لطفاً آن را ایجاد کنید.")
        return account

    @staticmethod
    def _get_category(category_name):
        """Returns a transaction category by name, or None if not found."""
        try:
            return TransactionCategory.objects.get(name=category_name)
        except TransactionCategory.DoesNotExist:
            return None

    @staticmethod
    def validate_discount(reservation):
        """Validates discount fields for a reservation."""
        if reservation.discount_amount is None:
            reservation.discount_amount = 0

        if reservation.discount_amount < 0:
            raise ValidationError('مبلغ تخفیف نمی‌تواند منفی باشد.')

        if reservation.rent_price is None:
            raise ValidationError('قیمت پایه رزرو مشخص نیست.')

        if reservation.discount_amount > reservation.rent_price:
            raise ValidationError('مبلغ تخفیف نمی‌تواند بیشتر از قیمت پایه باشد.')

    @staticmethod
    def calculate_final_price(reservation):
        """Calculates and sets the final price after discount."""
        ReservationFinancialService.validate_discount(reservation)
        rent_price = reservation.rent_price or 0
        discount = reservation.discount_amount or 0
        reservation.final_price = max(rent_price - discount, 0)
        return reservation.final_price

    @staticmethod
    def calculate_remaining_amount(reservation):
        """Calculates and sets the remaining amount to be paid."""
        final_price = reservation.final_price or 0
        deposit = reservation.deposit_amount or 0
        paid = reservation.remaining_payment_amount or 0
        refund = reservation.refunded_amount or 0
        damage = reservation.damage_amount or 0
        cancellation_fee = reservation.cancellation_fee or 0
        try:
            additional_fees = reservation.total_additional_fees() or 0
        except Exception:
            additional_fees = 0

        # Simplified calculation: final_price - (deposit + paid) + refunded + damages + fees
        # This might need adjustment based on accounting rules for refunds vs charges
        # For now, assuming direct cash flow impact
        total_paid_cash = deposit + paid
        total_charged_accrual = damage + cancellation_fee + additional_fees

        net_receivable = final_price + total_charged_accrual - total_paid_cash - refund

        reservation.remaining_amount = max(net_receivable, 0)
        return reservation.remaining_amount

    @staticmethod
    def update_financial_status(reservation):
        """Update calculated financial fields and payment status for a reservation."""
        if reservation is None:
            return None

        # Recalculate core reservation values based on current fields.
        reservation.final_price = ReservationFinancialService.calculate_final_price(reservation)
        reservation.remaining_amount = ReservationFinancialService.calculate_remaining_amount(reservation)

        paid_cash = ReservationFinancialService.current_paid_amount(reservation)
        refunded_amount = reservation.refunded_amount or 0
        net_cash = paid_cash - refunded_amount

        if net_cash <= 0:
            reservation.payment_status = (
                Reservation.PAYMENT_REFUNDED if refunded_amount > 0 else Reservation.PAYMENT_UNPAID
            )
        elif net_cash >= (reservation.final_price or 0):
            reservation.payment_status = Reservation.PAYMENT_PAID
        else:
            reservation.payment_status = Reservation.PAYMENT_PARTIAL

        return reservation

    @staticmethod
    def capture_base_snapshots(reservation):
        """Captures snapshots of related data if they haven't been captured yet."""
        if reservation.dress and reservation.dress_daily_price_snapshot is None:
            reservation.dress_daily_price_snapshot = reservation.dress.daily_rent_price

        if reservation.customer and not reservation.customer_phone_snapshot:
            reservation.customer_phone_snapshot = getattr(reservation.customer, 'bride_phone', '')

    @staticmethod
    def capture_financial_snapshot(reservation, event_type):
        """Captures a full financial snapshot at a key event."""
        # Ensure all base fields are calculated before snapshotting
        ReservationFinancialService.update_financial_status(reservation)

        # Use the latest actual values for snapshotting
        reservation.financial_snapshot = {
            'event_type': event_type,
            'captured_at': timezone.now().isoformat(),
            'status': reservation.status,
            'payment_status': reservation.payment_status,
            'final_price': reservation.final_price,
            'discount_amount': reservation.discount_amount,
            'deposit_amount': reservation.deposit_amount,
            'remaining_payment_amount': reservation.remaining_payment_amount,
            'refunded_amount': reservation.refunded_amount,
            'damage_amount': reservation.damage_amount,
            'cancellation_fee': reservation.cancellation_fee,
            'total_cash_collected': reservation.total_received_amount(), # Model method
            'remaining_amount': reservation.remaining_amount,
        }

    @staticmethod
    def synchronize_snapshot_fields(reservation):
        """Ensures all relevant financial fields and snapshots are up-to-date."""
        ReservationFinancialService.update_financial_status(reservation)
        # Explicitly capture a snapshot if the event warrants it (e.g., payment received)
        # The event_type would be passed by the calling service.

    @staticmethod
    def save_reservation_financials(reservation):
        """Saves the reservation after updating its financial fields."""
        # update_financial_status should be called before this to ensure fields are current
        # save_reservation_financials will then ensure the snapshot is captured if needed
        ReservationFinancialService.capture_financial_snapshot(reservation, 'update') # Capture state on save
        reservation.full_clean() # Perform model validations
        reservation.save()

    @staticmethod
    def validate_transaction_reference(payment_method, external_reference):
        if payment_method and payment_method != 'CASH' and not external_reference:
            raise ValidationError('برای روش پرداخت غیرنقدی باید کد رهگیری وارد شود.')

    @staticmethod
    def assert_positive_amount(amount, field_name='amount'):
        if amount is None or amount < 0:
            raise ValidationError(f'مقدار {field_name} باید عددی صفر یا مثبت باشد.')

    @staticmethod
    def current_paid_amount(reservation):
        """Calculates the total amount paid for a reservation, considering refunds."""
        # Use the aggregated totals from TransactionService for accurate calculation
        totals = TransactionService.aggregate_reservation_totals(reservation)

        cash_inflow = (
            (totals.get('total_deposit', 0) or 0)
            + (totals.get('total_final_payment', 0) or 0)
            + (totals.get('total_partial_payment', 0) or 0)
            + (totals.get('total_damage_payment', 0) or 0)
            + (totals.get('total_penalty_income', 0) or 0)
            - (totals.get('total_refund', 0) or 0)
        )
        return cash_inflow

    @staticmethod
    def get_financial_context(reservation):
        """Builds a financial summary dict for a reservation."""
        if reservation is None:
            return {}

        # Ensure the reservation's totals are up to date.
        ReservationFinancialService.update_financial_status(reservation)

        transactions = reservation.transactions.select_related('account', 'category', 'created_by').order_by('-transaction_date')
        totals = TransactionService.aggregate_reservation_totals(reservation)
        additional_fee_items = reservation.active_additional_fees().order_by('-created_at')
        additional_fee_total = reservation.total_additional_fees()

        return {
            'reservation': reservation,
            'transactions': transactions,
            'totals': {
                'deposit': totals.get('total_deposit', 0) or 0,
                'final_payment': totals.get('total_final_payment', 0) or 0,
                'damage_payment': totals.get('total_damage_payment', 0) or 0,
                'penalty_income': totals.get('total_penalty_income', 0) or 0,
                'refund': totals.get('total_refund', 0) or 0,
                'damage_charge': totals.get('total_damage_charge', 0) or 0,
                'discount': totals.get('total_discount', 0) or 0,
                'cancellation_fee': totals.get('total_cancellation_fee', 0) or 0,
                'adjustment': totals.get('total_adjustment', 0) or 0,
                'net_received': ReservationFinancialService.current_paid_amount(reservation),
                'remaining_amount': reservation.remaining_amount or 0,
                'final_price': reservation.final_price or 0,
                'refunded_amount': reservation.refunded_amount or 0,
                'damage_amount': reservation.damage_amount or 0,
                'additional_fees': additional_fee_total,
            },
            'payment_status': reservation.payment_status,
            'remaining_amount': reservation.remaining_amount or 0,
            'remaining_payment_amount': reservation.remaining_payment_amount or 0,
            'payment_method': reservation.payment_method,
            'payment_tracking_code': reservation.payment_tracking_code,
            'remaining_payment_method': reservation.remaining_payment_method,
            'remaining_payment_tracking_code': reservation.remaining_payment_tracking_code,
            'remaining_paid_at': reservation.remaining_paid_at,
            'additional_fee_items': additional_fee_items,
            'additional_fee_total': additional_fee_total,
        }

    @staticmethod
    def allowable_refund_amount(reservation):
        """Calculates the maximum amount that can be refunded for a reservation."""
        paid_cash = ReservationFinancialService.current_paid_amount(reservation)

        # Total due includes final price, damages, and cancellation fees.
        total_due_from_customer = (
            (reservation.final_price or 0) +
            (reservation.damage_amount or 0) +
            (reservation.cancellation_fee or 0)
        )

        refundable_amount = paid_cash - total_due_from_customer
        return max(refundable_amount, 0)
