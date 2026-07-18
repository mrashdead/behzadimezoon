import time

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import OperationalError
from django.utils import timezone

from financial.services.transaction_service import TransactionService
from financial.services.reservation_financial_service import ReservationFinancialService
from financial.models import FinancialAccount, TransactionCategory, Transaction
from reservations.constants import PaymentMethod, ReservationStatus
from reservations.models import Reservation


class PaymentService:
    @staticmethod
    def _validate_amount(amount, label):
        if amount is None or amount < 0:
            raise ValidationError(f'مقدار {label} باید عددی صفر یا مثبت باشد.')

    @staticmethod
    def get_penalty_payment_state(reservation, penalty_type):
        if penalty_type == 'CANCELLATION':
            cancellation_record = getattr(reservation, 'cancellation_record', None)
            total_penalty = reservation.cancellation_fee or 0
            if total_penalty <= 0 and cancellation_record is not None:
                total_penalty = cancellation_record.penalty_amount or 0
            paid_amount = reservation.cancellation_fee_paid_amount or 0
            remaining_amount = max(total_penalty - paid_amount, 0)
            if total_penalty <= 0:
                return {
                    'is_allowed': False,
                    'remaining_amount': 0,
                    'message': 'برای این رزرو جریمه لغو ثبت نشده است.',
                }
            if remaining_amount <= 0:
                return {
                    'is_allowed': False,
                    'remaining_amount': 0,
                    'message': 'جریمه لغو قبلاً به‌طور کامل پرداخت شده است.',
                }
            return {
                'is_allowed': True,
                'remaining_amount': remaining_amount,
                'message': '',
            }

        if penalty_type == 'DAMAGE':
            total_penalty = reservation.damage_amount or 0
            paid_amount = reservation.damage_fee_paid_amount or 0
            remaining_amount = max(total_penalty - paid_amount, 0)
            if total_penalty <= 0:
                return {
                    'is_allowed': False,
                    'remaining_amount': 0,
                    'message': 'برای این رزرو جریمه خسارت ثبت نشده است.',
                }
            if remaining_amount <= 0:
                return {
                    'is_allowed': False,
                    'remaining_amount': 0,
                    'message': 'جریمه خسارت قبلاً به‌طور کامل پرداخت شده است.',
                }
            return {
                'is_allowed': True,
                'remaining_amount': remaining_amount,
                'message': '',
            }

        raise ValidationError('نوع جریمه نامعتبر است.')

    @staticmethod
    def _validate_payment_reference(payment_method, external_reference):
        if payment_method and payment_method != 'CASH' and not external_reference:
            raise ValidationError('برای روش پرداخت غیرنقدی باید کد رهگیری وارد شود.')

    @staticmethod
    @transaction.atomic
    def record_deposit(reservation, amount, created_by, account=None, category=None, payment_method=None, external_reference=None, note=None, transaction_date=None, replace_existing=False):
        PaymentService._validate_amount(amount, 'بیعانه')
        PaymentService._validate_payment_reference(payment_method, external_reference)

        # Get default account and category if not provided
        if not account:
            account = FinancialAccount.objects.filter(account_type=FinancialAccount.AccountType.CASH).first()
        if not category:
            category = TransactionCategory.objects.filter(name='Deposit').first()

        tx = TransactionService.create_deposit(
            reservation=reservation,
            amount=amount,
            created_by=created_by,
            account=account,
            category=category,
            payment_method=payment_method,
            external_reference=external_reference,
            note=note or 'دریافت بیعانه',
            transaction_date=transaction_date,
        )

        # Update reservation financial fields and status
        if replace_existing:
            reservation.deposit_amount = amount
        else:
            reservation.deposit_amount = (reservation.deposit_amount or 0) + amount
        if payment_method:
            reservation.payment_method = payment_method
        if external_reference:
            reservation.payment_tracking_code = external_reference

        # Recalculate and update reservation financial status
        ReservationFinancialService.update_financial_status(reservation)
        ReservationFinancialService.capture_financial_snapshot(reservation, 'deposit')
        reservation.save()

        return tx

    @staticmethod
    @transaction.atomic
    def record_initial_deposit(reservation, amount, created_by, account=None, category=None, payment_method=None, external_reference=None, note=None):
        # This is essentially the same as record_deposit, kept for backward compatibility.
        return PaymentService.record_deposit(reservation, amount, created_by, account, category, payment_method, external_reference, note)

    @staticmethod
    @transaction.atomic
    def record_balance_payment(reservation, amount, created_by, account=None, category=None, payment_method=None, external_reference=None, note=None, transaction_date=None):
        PaymentService._validate_amount(amount, 'پرداخت باقی‌مانده')
        PaymentService._validate_payment_reference(payment_method, external_reference)

        transaction_date = transaction_date or timezone.now()

        # Get default account and category if not provided
        if not account:
            account = FinancialAccount.objects.filter(account_type=FinancialAccount.AccountType.CASH).first()
        if not category:
            category = TransactionCategory.objects.filter(name='Final Payment').first()

        tx = TransactionService.create_final_payment(
            reservation=reservation,
            amount=amount,
            created_by=created_by,
            account=account,
            category=category,
            payment_method=payment_method,
            external_reference=external_reference,
            note=note or 'پرداخت باقی‌مانده',
            transaction_date=transaction_date,
        )

        reservation.remaining_payment_amount = (reservation.remaining_payment_amount or 0) + amount
        reservation.remaining_payment_method = payment_method
        reservation.remaining_payment_tracking_code = external_reference
        reservation.remaining_paid_at = transaction_date

        ReservationFinancialService.update_financial_status(reservation)
        ReservationFinancialService.capture_financial_snapshot(reservation, 'balance_payment')
        reservation.save()
        return tx

    @staticmethod
    @transaction.atomic
    def record_installment_payment(reservation, amount, created_by, account=None, category=None, payment_method=None, external_reference=None, note=None, transaction_date=None):
        # Installment payments are treated as balance payments for simplicity
        return PaymentService.record_balance_payment(reservation, amount, created_by, account, category, payment_method, external_reference, note, transaction_date)

    @staticmethod
    @transaction.atomic
    def record_penalty_payment(reservation, amount, penalty_type, created_by, account=None, category=None, payment_method=None, external_reference=None, note=None, transaction_date=None):
        """
        ثبت پرداخت جریمه‌ها (لغو و خسارت)

        Args:
            reservation: رزرو مورد نظر
            amount: مبلغ جریمه
            penalty_type: نوع جریمه ('CANCELLATION' یا 'DAMAGE')
            created_by: کاربری که پرداخت را ثبت می‌کند
            account: حساب مالی (پیش‌فرض: صندوق)
            category: دسته‌بندی تراکنش (پیش‌فرض: درآمد)
            payment_method: روش پرداخت
            external_reference: کد رهگیری
            note: یادداشت
            transaction_date: تاریخ تراکنش
        """
        PaymentService._validate_payment_reference(payment_method, external_reference)

        try:
            amount = int(amount)
        except (TypeError, ValueError):
            raise ValidationError('مبلغ جریمه باید یک عدد صحیح باشد.')

        if amount <= 0:
            raise ValidationError('مبلغ جریمه باید بیشتر از صفر باشد.')

        transaction_date = transaction_date or timezone.now()

        if not account:
            account = FinancialAccount.objects.filter(account_type=FinancialAccount.AccountType.CASH).first()
        if not category:
            category = TransactionCategory.objects.filter(name='Penalty Income').first()

        reservation = Reservation.objects.select_for_update().get(pk=reservation.pk)
        state = PaymentService.get_penalty_payment_state(reservation, penalty_type)
        if not state['is_allowed']:
            raise ValidationError(state['message'])

        if amount > state['remaining_amount']:
            raise ValidationError(
                f'مبلغ پرداخت نمی‌تواند بیشتر از مانده جریمه ({state["remaining_amount"]:,} تومان) باشد.'
            )

        if penalty_type == 'CANCELLATION':
            tx_type = Transaction.TransactionType.PENALTY_INCOME
            default_note = 'پرداخت جریمه لغو'
        elif penalty_type == 'DAMAGE':
            tx_type = Transaction.TransactionType.PENALTY_INCOME
            default_note = 'پرداخت جریمه خسارت'
        else:
            raise ValidationError(f'نوع جریمه نامعتبر: {penalty_type}')

        tx = None
        for attempt in range(3):
            try:
                tx = TransactionService.create_transaction(
                    transaction_type=tx_type,
                    amount=amount,
                    reservation=reservation,
                    account=account,
                    category=category,
                    created_by=created_by,
                    payment_method=payment_method,
                    external_reference=external_reference,
                    note=note or default_note,
                    transaction_date=transaction_date,
                    transaction_status=Transaction.TransactionStatus.POSTED,
                )
                break
            except OperationalError as exc:
                if 'locked' not in str(exc).lower() or attempt == 2:
                    raise
                time.sleep(0.25)

        if tx is None:
            raise OperationalError('Failed to create penalty payment transaction after retries')

        if penalty_type == 'CANCELLATION':
            reservation.cancellation_fee_paid_amount = (reservation.cancellation_fee_paid_amount or 0) + amount
            reservation.cancellation_fee_payment_method = payment_method
            reservation.cancellation_fee_tracking_code = external_reference
            reservation.cancellation_fee_paid_at = transaction_date
        elif penalty_type == 'DAMAGE':
            reservation.damage_fee_paid_amount = (reservation.damage_fee_paid_amount or 0) + amount
            reservation.damage_fee_payment_method = payment_method
            reservation.damage_fee_tracking_code = external_reference
            reservation.damage_fee_paid_at = transaction_date

        ReservationFinancialService.update_financial_status(reservation)
        ReservationFinancialService.capture_financial_snapshot(reservation, 'penalty_payment')
        reservation.save()
        return tx
