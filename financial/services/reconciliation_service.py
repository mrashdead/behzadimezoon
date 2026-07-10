# financial/services/reconciliation_service.py

from django.db import transaction
from django.db.models import Sum, Case, When, Value, BigIntegerField, F
from django.utils import timezone
import datetime
from django.contrib.auth import get_user_model

from financial.models import Transaction, ReconciliationEntry, FinancialAccount
from financial.services.dashboard_service import DashboardService
from reservations.models import Reservation
from reservations.constants import ReservationStatus


class ReconciliationService:
    @staticmethod
    def _action_for_difference(cash_difference):
        """Determines suggested action based on cash difference."""
        if cash_difference > 0:
            return {
                'suggested_action': 'refund',
                'action_label': 'ثبت بازپرداخت',
                'transaction_type': Transaction.TransactionType.REFUND
            }
        if cash_difference < 0:
            return {
                'suggested_action': 'adjustment',
                'action_label': 'ثبت تعدیل',
                'transaction_type': Transaction.TransactionType.ADJUSTMENT_IN # Or ADJUSTMENT_OUT, depends on context
            }
        return {
            'suggested_action': 'none',
            'action_label': 'بدون اختلاف',
            'transaction_type': None
        }

    @staticmethod
    def reservation_discrepancies(reservation):
        """Calculates financial discrepancies for a single reservation."""
        # Use TransactionService for aggregated totals which are more reliable
        from financial.services.transaction_service import TransactionService
        totals = TransactionService.aggregate_reservation_totals(reservation)

        expected_cash_from_transactions = (
            (totals.get('total_deposit', 0) or 0)
            + (totals.get('total_final_payment', 0) or 0)
            + (totals.get('total_partial_payment', 0) or 0)
            + (totals.get('total_damage_payment', 0) or 0)
            - (totals.get('total_refund', 0) or 0)
            + (totals.get('total_adjustment', 0) or 0)
        )

        # Use reservation model fields for comparison (as it holds the state)
        reservation_cash_recorded = (
            (reservation.deposit_amount or 0)
            + (reservation.remaining_payment_amount or 0)
            - (reservation.refunded_amount or 0)
        )

        cash_difference = expected_cash_from_transactions - reservation_cash_recorded

        # Suggest action based on difference
        action = ReconciliationService._action_for_difference(cash_difference)

        return {
            'reservation_id': reservation.pk,
            'customer_name': str(reservation.customer) if reservation.customer else 'ـ',
            'dress_code': reservation.dress.code if reservation.dress else 'ـ',
            'expected_cash': expected_cash_from_transactions,
            'expected_cash_from_tx': expected_cash_from_transactions,
            'reservation_cash_recorded': reservation_cash_recorded,
            'cash_difference': cash_difference,
            'suggested_action': action['suggested_action'],
            'action_label': action['action_label'],
            'transaction_type': action['transaction_type'],
            'has_discrepancy': cash_difference != 0,
            'open_receivable': max(0, (totals.get('total_damage_charge', 0) or 0) + (totals.get('total_cancellation_fee', 0) or 0) - (totals.get('total_damage_payment', 0) or 0)), # Based on charges vs payments
        }

    @staticmethod
    def get_open_problem_reservations(filters=None):
        """Finds reservations with financial discrepancies."""
        filters = filters or {}

        reservations_qs = Reservation.objects.filter(
            status__in=[ReservationStatus.CONFIRMED, ReservationStatus.DELIVERED, ReservationStatus.RETURNED]
        )
        reservations_qs = DashboardService._apply_reservation_filters(reservations_qs, filters) # Apply filters if provided

        discrepancies = []
        for reservation in reservations_qs:
            # Check for open issues like pending reconciliation or overdue payments
            if reservation.payment_status == Reservation.PAYMENT_PARTIAL and reservation.due_date and reservation.due_date < timezone.localdate():
                # This reservation has a partial payment and is overdue
                discrepancies.append({
                    'reservation_id': reservation.id,
                    'customer_name': str(reservation.customer),
                    'dress_code': str(reservation.dress.code) if reservation.dress else '-',
                    'issue': 'پرداخت معوق',
                    'details': f'تاریخ سررسید: {reservation.due_date}'
                })

            # Check for financial discrepancies using the service
            financial_data = ReconciliationService.reservation_discrepancies(reservation)
            if financial_data['has_discrepancy']:
                diff = financial_data['cash_difference']
                action = financial_data['action_label']
                discrepancies.append({
                    'reservation_id': reservation.id,
                    'customer_name': str(reservation.customer),
                    'dress_code': str(reservation.dress.code) if reservation.dress else '-',
                    'issue': 'اختلاف مالی',
                    'details': f'تفاوت: {diff} | پیشنهاد: {action}',
                })

        return discrepancies

    @staticmethod
    def get_unreconciled_transactions(account_id=None):
        """Retrieves transactions that are not yet reconciled."""
        qs = Transaction.objects.filter(is_reconciled=False, transaction_status=Transaction.TransactionStatus.POSTED)
        if account_id:
            qs = qs.filter(account_id=account_id)
        return qs.order_by('transaction_date')

    @staticmethod
    @transaction.atomic
    def reconcile_transactions(transaction_ids, reconciliation_entry):
        """Marks transactions as reconciled and updates reconciliation entry."""
        if not transaction_ids:
            raise ValueError('هیچ تراکنشی برای هماهنگی انتخاب نشده است.')

        # Mark transactions as reconciled
        Transaction.objects.filter(id__in=transaction_ids).update(is_reconciled=True, reconciled_at=timezone.now())

        # Update reconciliation entry status
        reconciliation_entry.status = ReconciliationEntry.Status.RESOLVED
        reconciliation_entry.resolved_by = get_user_model().objects.get(pk=1) # Placeholder for user
        reconciliation_entry.resolved_at = timezone.now()
        reconciliation_entry.save()

        return True
