from django.core.exceptions import ValidationError
from django.utils import timezone

from financial.services.transaction_service import TransactionService
from reservations.constants import PaymentMethod
from reservations.models import Reservation


class ReservationFinancialService:
    @staticmethod
    def validate_discount(reservation):
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
        ReservationFinancialService.validate_discount(reservation)
        rent_price = reservation.rent_price or 0
        discount = reservation.discount_amount or 0
        reservation.final_price = max(rent_price - discount, 0)
        return reservation.final_price

    @staticmethod
    def calculate_remaining_amount(reservation):
        final_price = reservation.final_price or 0
        deposit = reservation.deposit_amount or 0
        paid = reservation.remaining_payment_amount or 0
        refund = reservation.refunded_amount or 0
        damage = reservation.damage_amount or 0
        cancellation_fee = reservation.cancellation_fee or 0

        remaining = final_price - deposit - paid + refund + damage + cancellation_fee
        reservation.remaining_amount = max(remaining, 0)
        return reservation.remaining_amount

    @staticmethod
    def capture_base_snapshots(reservation):
        if reservation.dress and reservation.dress_daily_price_snapshot is None:
            reservation.dress_daily_price_snapshot = reservation.dress.daily_rent_price

        if reservation.customer and not reservation.customer_phone_snapshot:
            reservation.customer_phone_snapshot = getattr(reservation.customer, 'bride_phone', '')

    @staticmethod
    def capture_financial_snapshot(reservation, event_type):
        reservation.financial_snapshot = {
            'event_type': event_type,
            'captured_at': timezone.now().isoformat(),
            'final_price': reservation.final_price,
            'discount_amount': reservation.discount_amount,
            'deposit_amount': reservation.deposit_amount,
            'remaining_payment_amount': reservation.remaining_payment_amount,
            'refunded_amount': reservation.refunded_amount,
            'damage_amount': reservation.damage_amount,
            'cancellation_fee': reservation.cancellation_fee,
            'total_cash_collected': reservation.total_received_amount(),
            'remaining_amount': reservation.remaining_amount,
        }

    @staticmethod
    def synchronize_snapshot_fields(reservation):
        ReservationFinancialService.capture_base_snapshots(reservation)
        ReservationFinancialService.calculate_final_price(reservation)
        ReservationFinancialService.calculate_remaining_amount(reservation)
        reservation.total_cash_collected_snapshot = reservation.total_received_amount()

    @staticmethod
    def save_reservation_financials(reservation):
        ReservationFinancialService.synchronize_snapshot_fields(reservation)
        reservation.full_clean()
        reservation.save()

    @staticmethod
    def validate_transaction_reference(payment_method, external_reference):
        if payment_method and payment_method != PaymentMethod.CASH and not external_reference:
            raise ValidationError('برای روش پرداخت غیرنقدی باید کد رهگیری وارد شود.')

    @staticmethod
    def assert_positive_amount(amount, field_name='amount'):
        if amount is None or amount < 0:
            raise ValidationError(f'مقدار {field_name} باید عددی صفر یا مثبت باشد.')

    @staticmethod
    def current_paid_amount(reservation):
        from financial.services.transaction_service import TransactionService

        totals = TransactionService.aggregate_reservation_totals(reservation)
        return (
            (totals.get('total_deposit') or 0)
            + (totals.get('total_final_payment') or 0)
            + (totals.get('total_damage_payment') or 0)
            - (totals.get('total_refund') or 0)
        )

    @staticmethod
    def allowable_refund_amount(reservation):
        paid = ReservationFinancialService.current_paid_amount(reservation)
        total_due = (reservation.final_price or 0) + (reservation.damage_amount or 0) + (reservation.cancellation_fee or 0)
        refundable = paid - total_due
        return max(refundable, 0)
