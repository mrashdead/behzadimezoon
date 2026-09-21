# financial/views_reconcile.py

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView
from django.utils import timezone
from django.contrib import messages

from financial.services.reconciliation_service import ReconciliationService
from financial.services.transaction_service import TransactionService
from financial.services.dashboard_service import DashboardService # Needed for _apply_reservation_filters
from financial.models import Transaction, FinancialAccount, TransactionCategory, ReconciliationEntry
from reservations.models import Reservation
from accounts.models import User # Assuming User model from accounts app


def superuser_required(user):
    return getattr(user, 'role', None) == User.Role.SUPER_ADMIN or user.is_superuser


class ReconciliationAdminPageView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'financial/reconcile_admin.html'

    def test_func(self):
        return superuser_required(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'هماهنگی مالی و رفع اختلافات'

        # ------------------------------------------------------------------
        # فیلترها
        # ------------------------------------------------------------------
        # توجه: ``ReconciliationService.get_open_problem_reservations`` فقط
        # ``date_from`` / ``date_to`` (و ``seller_id``) را می‌فهمد؛ کلید
        # ``reservation_id`` در ``DashboardService._apply_reservation_filters``
        # نادیده گرفته می‌شود. پس فیلتر شناسهٔ رزرو را بعد از ساخت فهرست،
        # این‌جا اعمال می‌کنیم تا فیلترِ رابط کاربری واقعاً کار کند.
        date_from = self.request.GET.get('date_from') or None
        date_to = self.request.GET.get('date_to') or None
        reservation_id = (self.request.GET.get('reservation_id') or '').strip()

        service_filters = {
            'date_from': date_from,
            'date_to': date_to,
        }

        # Get open discrepancies
        open_discrepancies = ReconciliationService.get_open_problem_reservations(service_filters)

        if reservation_id:
            if reservation_id.isdigit():
                target_id = int(reservation_id)
                open_discrepancies = [
                    item for item in open_discrepancies
                    if item.get('reservation_id') == target_id
                ]
            else:
                # ورودی غیرعددی → نتیجهٔ خالی، ولی با پیام روشن در قالب.
                open_discrepancies = []

        context['problems'] = open_discrepancies
        context['open_issues_count'] = len(open_discrepancies)

        # شمارش تفکیکی بر اساس نوع مشکل (برای کارت‌های خلاصه)
        overdue_count = sum(1 for item in open_discrepancies if item.get('kind') == 'overdue')
        discrepancy_count = sum(1 for item in open_discrepancies if item.get('kind') == 'discrepancy')
        context['overdue_count'] = overdue_count
        context['discrepancy_count'] = discrepancy_count
        context['distinct_reservations_count'] = len({
            item.get('reservation_id') for item in open_discrepancies
        })

        # جمع قدرمطلق اختلاف‌ها و مبلغ پیشنهادی بازپرداخت
        differences = [
            abs(item.get('cash_difference') or 0)
            for item in open_discrepancies
            if item.get('kind') == 'discrepancy'
        ]
        context['total_absolute_difference'] = sum(differences)
        context['refund_suggested_total'] = sum(
            (item.get('cash_difference') or 0)
            for item in open_discrepancies
            if item.get('suggested_action') == 'refund'
        )
        context['open_receivable_total'] = sum(
            (item.get('open_receivable') or 0) for item in open_discrepancies
        )

        # Get unreconciled transactions (for manual reconciliation)
        unreconciled_transactions = ReconciliationService.get_unreconciled_transactions()
        context['unreconciled_transactions'] = unreconciled_transactions[:20]  # Show a few
        context['unreconciled_count'] = unreconciled_transactions.count()
        context['unreconciled_total'] = (
            unreconciled_transactions.aggregate(total=Sum('amount'))['total'] or 0
        )

        # وضعیت فیلترها برای نمایش در سربرگ
        context['filter_date_from'] = date_from or ''
        context['filter_date_to'] = date_to or ''
        context['filter_reservation_id'] = reservation_id
        context['has_active_filters'] = bool(date_from or date_to or reservation_id)

        return context


@login_required
@user_passes_test(superuser_required)
@require_POST
def reconciliation_resolve_view(request):
    reservation_id = request.POST.get('reservation_id')
    if not reservation_id:
        return JsonResponse({'error': 'reservation_id required'}, status=400)

    try:
        reservation = get_object_or_404(Reservation, pk=reservation_id)
    except Exception:
        return JsonResponse({'error': 'رزرو یافت نشد.'}, status=404)

    discrepancy = ReconciliationService.reservation_discrepancies(reservation)
    diff = discrepancy.get('cash_difference', 0)

    if diff == 0:
        return JsonResponse({'result': 'no-op', 'message': 'هیچ اختلافی برای تسویه وجود ندارد.'}, status=200)

    # Get or create a default cash account and adjustment category
    cash_account, _ = FinancialAccount.objects.get_or_create(
        account_type=FinancialAccount.AccountType.CASH,
        defaults={
            'code': 'CASH_DEFAULT',
            'name': 'حساب نقدی پیش‌فرض',
            'balance': 0,
            'description': 'Default cash account used for reconciliation adjustments.',
            'is_active': True,
        }
    )

    adjustment_category, _ = TransactionCategory.objects.get_or_create(
        name='Adjustment',
        defaults={
            'category_type': TransactionCategory.CategoryType.ADJUSTMENT,
            'description': 'Adjustment category for reconciliation actions.',
            'color': '#6c757d',
        }
    )

    try:
        if discrepancy['suggested_action'] == 'refund': # means transactions are higher than reservation model
            tx = TransactionService.create_refund(
                reservation=reservation,
                amount=abs(diff),
                created_by=request.user,
                account=cash_account,
                category=adjustment_category,
                note=f'بازپرداخت تعدیل شده برای اختلاف رزرو #{reservation.id}',
                transaction_date=timezone.now(),
            )
            message = f'بازپرداخت تعدیلی به مبلغ {abs(diff)} تومان ثبت شد.'
        elif discrepancy['suggested_action'] == 'adjustment': # means reservation model is higher than transactions
            tx = TransactionService.create(
                reservation=reservation,
                transaction_type=Transaction.TransactionType.ADJUSTMENT,
                amount=abs(diff),
                created_by=request.user,
                account=cash_account,
                category=adjustment_category,
                description=f'تعدیل برای اختلاف رزرو #{reservation.id}',
                transaction_date=timezone.now(),
            )
            message = f'تعدیل به مبلغ {abs(diff)} تومان ثبت شد.'
        else:
            return JsonResponse({'error': 'اقدام تسویه نامشخص.'}, status=400)

        messages.success(request, message)
        return JsonResponse({
            'result': 'ok',
            'transaction_id': tx.pk,
            'action': discrepancy['suggested_action'],
            'message': message,
        })
    except Exception as e:
        print('RECONCILE ERROR:', e)
        traceback.print_exc()
        messages.error(request, f'خطا در ثبت تراکنش تسویه: {str(e)}.')
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@user_passes_test(superuser_required)
@require_POST
def reconcile_transactions_manual_view(request):
    transaction_ids = request.POST.getlist('transaction_ids') # list of transaction IDs to reconcile
    if not transaction_ids:
        return JsonResponse({'error': 'هیچ تراکنشی برای هماهنگی انتخاب نشده است.'}, status=400)

    try:
        # Create a new ReconciliationEntry
        reconciliation_entry = ReconciliationEntry.objects.create(
            reconciliation_date=timezone.localdate(), # For today's date
            opening_balance=0, # These would be dynamic in a real scenario
            closing_balance=0,
            difference=0,
            status=ReconciliationEntry.Status.OPEN,
            notes='هماهنگی دستی توسط ادمین'
        )

        # Call the service to mark transactions as reconciled
        ReconciliationService.reconcile_transactions(transaction_ids, reconciliation_entry)
        messages.success(request, 'تراکنش‌های انتخاب‌شده با موفقیت هماهنگ شدند.')
        return JsonResponse({'success': True, 'message': 'تراکنش‌ها هماهنگ شدند.'})
    except Exception as e:
        messages.error(request, f'خطا در هماهنگی تراکنش‌ها: {str(e)}.')
        return JsonResponse({'error': str(e)}, status=500)
