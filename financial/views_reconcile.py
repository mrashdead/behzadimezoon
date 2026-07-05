from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from financial.services.reconciliation_service import ReconciliationService
from financial.services.transaction_service import TransactionService
from financial.models import Transaction


def superuser_required(user):
    return getattr(user, 'is_superuser', False)


@login_required
@user_passes_test(superuser_required)
def reconciliation_admin_view(request):
    service = ReconciliationService()
    problems = service.get_open_problem_reservations()
    # problems is a list of dicts
    return JsonResponse({'problems': problems})


class ReconciliationAdminPageView(TemplateView):
    template_name = 'financial/reconcile_admin.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'تسویه مالی'
        context['problems'] = ReconciliationService.get_open_problem_reservations()
        return context


@login_required
@user_passes_test(superuser_required)
@require_POST
def reconciliation_resolve_view(request):
    reservation_id = request.POST.get('reservation_id')
    if not reservation_id:
        return JsonResponse({'error': 'reservation_id required'}, status=400)

    service = ReconciliationService()
    try:
        from reservations.models import Reservation
        reservation = Reservation.objects.get(pk=reservation_id)
    except Exception:
        return JsonResponse({'error': 'reservation not found'}, status=404)

    discrepancy = service.reservation_discrepancies(reservation)
    diff = discrepancy.get('cash_difference', 0)

    if diff == 0:
        return JsonResponse({'result': 'no-op', 'message': 'هیچ اختلافی برای تسویه وجود ندارد.'}, status=200)

    if discrepancy['suggested_action'] == 'refund':
        tx = TransactionService.create_refund(
            reservation=reservation,
            amount=diff,
            created_by=request.user,
            note='بازپرداخت شناسایی شده توسط تسویه مالی',
            external_reference='reconcile-admin'
        )
        message = f'بازپرداخت به مبلغ {diff} تومان ثبت شد.'
    else:
        tx = TransactionService.create(
            reservation=reservation,
            transaction_type=Transaction.Type.ADJUSTMENT,
            amount=abs(diff),
            created_by=request.user,
            note='تعدیل شناسایی شده توسط تسویه مالی',
            external_reference='reconcile-admin'
        )
        message = f'تعدیل به مبلغ {abs(diff)} تومان ثبت شد.'

    return JsonResponse({
        'result': 'ok',
        'transaction_id': tx.pk,
        'action': discrepancy['suggested_action'],
        'message': message,
    })
