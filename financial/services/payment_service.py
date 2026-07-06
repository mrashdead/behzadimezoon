from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from financial.services.transaction_service import TransactionService
from financial.services.reservation_financial_service import ReservationFinancialService
from reservations.constants import PaymentMethod


class PaymentService:
    @staticmethod
    def _validate_amount(amount, label):
        if amount is None or amount < 0:
            raise ValidationError(f'مقدار {label} باید عددی صفر یا مثبت باشد.')

    @staticmethod
    def _validate_payment_reference(payment_method, external_reference):
        if payment_method and payment_method != PaymentMethod.CASH and not external_reference:
            raise ValidationError('برای روش پرداخت غیرنقدی باید کد رهگیری وارد شود.')

    @staticmethod
    def record_deposit(reservation, amount, created_by, payment_method=None, external_reference=None, note=None):
        PaymentService._validate_amount(amount, 'بیعانه')
        PaymentService._validate_payment_reference(payment_method, external_reference)

        with transaction.atomic():
            tx = TransactionService.create_deposit(
                reservation=reservation,
                amount=amount,
                created_by=created_by,
                payment_method=payment_method,
                external_reference=external_reference,
                note=note or 'دریافت بیعانه'
            )

            reservation.deposit_amount = (reservation.deposit_amount or 0) + amount
            if payment_method:
                reservation.payment_method = payment_method
            if external_reference:
                reservation.payment_tracking_code = external_reference
            ReservationFinancialService.synchronize_snapshot_fields(reservation)
            ReservationFinancialService.capture_financial_snapshot(reservation, 'deposit')
            reservation.save()
            return tx

    @staticmethod
    def record_initial_deposit(reservation, amount, created_by, payment_method=None, external_reference=None, note=None):
        PaymentService._validate_amount(amount, 'بیعانه')
        PaymentService._validate_payment_reference(payment_method, external_reference)

        with transaction.atomic():
            tx = TransactionService.create_deposit(
                reservation=reservation,
                amount=amount,
                created_by=created_by,
                payment_method=payment_method,
                external_reference=external_reference,
                note=note or 'بیعانه رزرو ثبت شد'
            )
            if payment_method:
                reservation.payment_method = payment_method
            if external_reference:
                reservation.payment_tracking_code = external_reference
            ReservationFinancialService.synchronize_snapshot_fields(reservation)
            ReservationFinancialService.capture_financial_snapshot(reservation, 'deposit')
            reservation.save()
            return tx

    @staticmethod
    def record_balance_payment(reservation, amount, created_by, payment_method=None, external_reference=None, note=None, transaction_date=None):
        PaymentService._validate_amount(amount, 'پرداخت باقی‌مانده')
        PaymentService._validate_payment_reference(payment_method, external_reference)

        transaction_date = transaction_date or timezone.now()
        with transaction.atomic():
            tx = TransactionService.create_final_payment(
                reservation=reservation,
                amount=amount,
                created_by=created_by,
                payment_method=payment_method,
                external_reference=external_reference,
                note=note or 'پرداخت باقی‌مانده',
                transaction_date=transaction_date,
            )

            reservation.remaining_payment_amount = (reservation.remaining_payment_amount or 0) + amount
            reservation.remaining_payment_method = payment_method
            reservation.remaining_payment_tracking_code = external_reference
            reservation.remaining_paid_at = transaction_date
            ReservationFinancialService.synchronize_snapshot_fields(reservation)
            ReservationFinancialService.capture_financial_snapshot(reservation, 'balance_payment')
            reservation.save()
            return tx

    @staticmethod
    def record_installment_payment(reservation, amount, created_by, payment_method=None, external_reference=None, note=None, transaction_date=None):
        return PaymentService.record_balance_payment(
            reservation=reservation,
            amount=amount,
            created_by=created_by,
            payment_method=payment_method,
            external_reference=external_reference,
            note=note or 'پرداخت اقساطی',
            transaction_date=transaction_date,
        )
