# financial/services/kpi_service.py

from django.db.models import Sum, Count, Q, Case, When, Value, BigIntegerField
from django.utils import timezone
import datetime

from financial.models import Transaction, FinancialAccount
from reservations.models import Reservation
from reservations.constants import ReservationStatus


class KPIService:
    @staticmethod
    def _income_transaction_types():
        return [
            Transaction.TransactionType.DEPOSIT,
            Transaction.TransactionType.FINAL_PAYMENT,
            Transaction.TransactionType.PARTIAL_PAYMENT,
            Transaction.TransactionType.PAYMENT,
            Transaction.TransactionType.DAMAGE_PAYMENT,
            Transaction.TransactionType.PENALTY_INCOME,
            Transaction.TransactionType.TRANSFER_IN,
            Transaction.TransactionType.ADJUSTMENT_IN,
        ]

    @staticmethod
    def _expense_transaction_types():
        return [
            Transaction.TransactionType.LAUNDRY_EXPENSE,
            Transaction.TransactionType.REPAIR_EXPENSE,
            Transaction.TransactionType.SUPPLY_EXPENSE,
            Transaction.TransactionType.UTILITY_EXPENSE,
            Transaction.TransactionType.STAFF_SALARY,
            Transaction.TransactionType.RENT_EXPENSE,
            Transaction.TransactionType.MARKETING_EXPENSE,
            Transaction.TransactionType.TRANSFER_OUT,
            Transaction.TransactionType.ADJUSTMENT_OUT,
        ]

    @staticmethod
    def get_overall_financial_kpis():
        """محاسبه شاخص‌های کلیدی مالی کلی."""
        posted_transactions = Transaction.objects.filter(
            transaction_status=Transaction.TransactionStatus.POSTED,
            is_voided=False,
        )

        total_revenue = (
            posted_transactions.filter(
                transaction_type__in=KPIService._income_transaction_types()
            ).aggregate(total=Sum('amount'))['total'] or 0
        )
        total_expenses = (
            posted_transactions.filter(
                transaction_type__in=KPIService._expense_transaction_types()
            ).aggregate(total=Sum('amount'))['total'] or 0
        )
        net_profit = total_revenue - total_expenses

        receivables = Reservation.objects.filter(
            payment_status__in=[Reservation.PAYMENT_PARTIAL, Reservation.PAYMENT_UNPAID],
            status__in=[ReservationStatus.CONFIRMED, ReservationStatus.DELIVERED],
        ).aggregate(total_receivables=Sum('remaining_amount'))['total_receivables'] or 0

        today = timezone.localdate()
        start_of_day = timezone.make_aware(
            datetime.datetime(today.year, today.month, today.day)
        )
        end_of_day = start_of_day + datetime.timedelta(days=1)

        today_income = (
            posted_transactions.filter(
                transaction_date__gte=start_of_day,
                transaction_date__lt=end_of_day,
                transaction_type__in=KPIService._income_transaction_types(),
            ).aggregate(total=Sum('amount'))['total'] or 0
        )

        start_of_month = today.replace(day=1)
        end_of_month = (start_of_month + datetime.timedelta(days=32)).replace(day=1)
        this_month_income = (
            posted_transactions.filter(
                transaction_date__gte=start_of_month,
                transaction_date__lt=end_of_month,
                transaction_type__in=KPIService._income_transaction_types(),
            ).aggregate(total=Sum('amount'))['total'] or 0
        )

        return {
            'total_revenue': total_revenue,
            'total_expenses': total_expenses,
            'net_profit': net_profit,
            'receivables': receivables,
            'payables': 0,
            'today_income': today_income,
            'this_month_income': this_month_income,
        }

    @staticmethod
    def get_reservation_financial_kpis(reservation):
        """محاسبه شاخص‌های مالی اختصاصی یک رزرو."""
        from financial.services.transaction_service import TransactionService

        totals = TransactionService.aggregate_reservation_totals(reservation)

        total_deposit = totals.get('total_deposit', 0) or 0
        total_final = totals.get('total_final_payment', 0) or 0
        total_partial = totals.get('total_partial_payment', 0) or 0
        total_damage_payment = totals.get('total_damage_payment', 0) or 0
        total_penalty_income = totals.get('total_penalty_income', 0) or 0
        total_refund = totals.get('total_refund', 0) or 0
        total_damage_charge = totals.get('total_damage_charge', 0) or 0
        total_cancellation_fee = totals.get('total_cancellation_fee', 0) or 0

        paid_amount = (total_deposit + total_final + total_partial + total_damage_payment + total_penalty_income) - total_refund
        net_receivable = (
            reservation.final_price + total_damage_charge + total_cancellation_fee - paid_amount
        )

        return {
            'total_paid': paid_amount,
            'remaining_due': max(0, net_receivable),
            'total_refunded': total_refund,
            'total_charges': total_damage_charge + total_cancellation_fee,
        }

    @staticmethod
    def get_account_balances_kpi():
        """محاسبه شاخص‌های تراز حساب‌های مالی."""
        balances = FinancialAccount.objects.aggregate(
            total_cash=Sum(Case(When(account_type='CASH', then='balance'), default=Value(0), output_field=BigIntegerField())),
            total_bank=Sum(Case(When(account_type='BANK', then='balance'), default=Value(0), output_field=BigIntegerField())),
            total_receivable=Sum(Case(When(account_type='RECEIVABLE', then='balance'), default=Value(0), output_field=BigIntegerField())),
            total_expense_accounts=Sum(Case(When(account_type='EXPENSE', then='balance'), default=Value(0), output_field=BigIntegerField())),
        )
        return balances
