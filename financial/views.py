from django.contrib.auth.decorators import login_required
from django.db.utils import ProgrammingError
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from io import BytesIO

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from financial.services.reconciliation_service import ReconciliationService
from financial.services.transaction_service import TransactionService
from financial.services.payment_service import PaymentService
from financial.services.refund_service import RefundService
from financial.services.dashboard_service import DashboardService
from financial.services.export_service import FinancialExportService
from financial.models import FinancialAccount, TransactionCategory
from financial.forms import TransactionForm
from reservations.models import AdditionalFee, Reservation
from accounts.models import User


@method_decorator(login_required, name='dispatch')
class FinancialDashboardView(TemplateView):
    template_name = 'financial/list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = {
            'date_from': self.request.GET.get('date_from'),
            'date_to': self.request.GET.get('date_to'),
            'seller_id': self.request.GET.get('seller'),
            'ledger_mode': self.request.GET.get('ledger', None),
        }

        reporting = {}
        try:
            financial_ctx = DashboardService.get_financial_context(filters=params)
            totals = financial_ctx.get('totals', {})
            cancelled_totals = financial_ctx.get('cancelled_totals', {})
            recent_reservations = financial_ctx.get('recent_reservations', [])
            uses_transaction_ledger = financial_ctx.get('uses_transaction_ledger', False)
            open_reconciliation_issues = financial_ctx.get('open_reconciliation_issues', 0)
            reporting = financial_ctx.get('reporting', {})
        except ProgrammingError:
            totals = {
                'total_reservations': 0,
                'total_revenue': 0,
                'total_gross_rent': 0,
                'total_discounts': 0,
                'total_deposit': 0,
                'total_remaining': 0,
                'total_damage_received': 0,
                'total_cash_inflow': 0,
                'total_refunded': 0,
                'total_additional_fee_revenue': 0,
            }
            cancelled_totals = {
                'total_cancelled_reservations': 0,
                'cancelled_received_amount': 0,
                'cancelled_damage_received': 0,
                'cancelled_refunded_amount': 0,
            }
            recent_reservations = Reservation.objects.none()
            uses_transaction_ledger = False
            open_reconciliation_issues = 0
            reporting = {}

        context['page_title'] = 'مالی'
        context['totals'] = totals
        context['cancelled_totals'] = cancelled_totals
        context['recent_reservations'] = recent_reservations
        context['uses_transaction_ledger'] = uses_transaction_ledger
        context['open_reconciliation_issues'] = open_reconciliation_issues
        context['reporting'] = reporting
        context['sellers'] = User.objects.filter(role='SELLER')
        return context


@login_required
def api_reservation_search(request):
    query = request.GET.get('q', '').strip()
    reservations = Reservation.objects.filter(is_deleted=False)

    if query:
        if query.isdigit():
            reservations = reservations.filter(pk=query)
        else:
            reservations = reservations.filter(
                Q(customer__bride_first_name__icontains=query)
                | Q(customer__bride_last_name__icontains=query)
                | Q(dress__code__icontains=query)
                | Q(payment_tracking_code__icontains=query)
            )

    reservations = reservations.order_by('-created_at')[:20]
    results = [
        {
            'id': r.pk,
            'label': f"#{r.pk} {r.customer} / {r.dress}",
            'final_price': r.final_price or 0,
            'deposit_amount': r.deposit_amount or 0,
            'remaining_amount': r.remaining_amount or 0,
            'payment_status': r.payment_status,
            'status': r.status,
        }
        for r in reservations
    ]
    return JsonResponse({'results': results})


@login_required
def api_reservation_info(request):
    reservation_id = request.GET.get('id') or request.GET.get('reservation_id')
    if not reservation_id:
        return JsonResponse({'error': 'reservation_id is required.'}, status=400)

    try:
        reservation = Reservation.objects.get(pk=reservation_id, is_deleted=False)
    except Reservation.DoesNotExist:
        return JsonResponse({'error': 'رزرو پیدا نشد.'}, status=404)

    return JsonResponse({
        'id': reservation.pk,
        'customer': str(reservation.customer),
        'dress': str(reservation.dress),
        'final_price': reservation.final_price or 0,
        'deposit_amount': reservation.deposit_amount or 0,
        'remaining_amount': reservation.remaining_amount or 0,
        'payment_status': reservation.payment_status,
        'payment_method': reservation.payment_method,
        'remaining_payment_method': reservation.remaining_payment_method,
        'start_date': reservation.start_date.isoformat() if reservation.start_date else None,
    })


@login_required
@require_POST
def record_payment_view(request):
    reservation_id = request.POST.get('reservation_id')
    transaction_type = request.POST.get('type', 'DEPOSIT')
    amount = request.POST.get('amount')
    payment_method = request.POST.get('payment_method')
    external_reference = request.POST.get('external_reference')
    note = request.POST.get('note', '')

    if not reservation_id or not amount:
        return JsonResponse({'error': 'reservation_id و amount الزامی است.'}, status=400)

    try:
        amount = int(amount)
    except ValueError:
        return JsonResponse({'error': 'مبلغ باید عددی صحیح باشد.'}, status=400)

    try:
        reservation = Reservation.objects.get(pk=reservation_id, is_deleted=False)
    except Reservation.DoesNotExist:
        return JsonResponse({'error': 'رزرو یافت نشد.'}, status=404)

    try:
        if transaction_type == 'DEPOSIT':
            tx = PaymentService.record_deposit(
                reservation=reservation,
                amount=amount,
                created_by=request.user,
                payment_method=payment_method,
                external_reference=external_reference,
                note=note or 'ثبت بیعانه دستی'
            )
        elif transaction_type == 'FINAL_PAYMENT':
            tx = PaymentService.record_balance_payment(
                reservation=reservation,
                amount=amount,
                created_by=request.user,
                payment_method=payment_method,
                external_reference=external_reference,
                note=note or 'ثبت پرداخت نهایی دستی'
            )
        elif transaction_type == 'REFUND':
            tx = RefundService.record_refund(
                reservation=reservation,
                amount=amount,
                created_by=request.user,
                payment_method=payment_method,
                external_reference=external_reference,
                note=note or 'ثبت بازپرداخت دستی'
            )
        else:
            tx = TransactionService.create(
                reservation=reservation,
                transaction_type=transaction_type,
                amount=amount,
                created_by=request.user,
                payment_method=payment_method,
                payment_reference=external_reference,
                description=note,
            )
        return JsonResponse({'result': 'ok', 'transaction_id': tx.pk, 'message': 'پرداخت ثبت شد.'})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=400)


@login_required
@require_POST
def record_expense_view(request):
    reservation_id = request.POST.get('reservation_id')
    transaction_type = request.POST.get('transaction_type', 'LAUNDRY_EXPENSE')
    amount = request.POST.get('amount')
    payment_method = request.POST.get('payment_method')
    external_reference = request.POST.get('external_reference')
    note = request.POST.get('note', '')

    if not reservation_id or not amount:
        return JsonResponse({'error': 'reservation_id و amount الزامی است.'}, status=400)

    try:
        amount = int(amount)
    except ValueError:
        return JsonResponse({'error': 'مبلغ باید عددی صحیح باشد.'}, status=400)

    try:
        reservation = Reservation.objects.get(pk=reservation_id, is_deleted=False)
    except Reservation.DoesNotExist:
        return JsonResponse({'error': 'رزرو یافت نشد.'}, status=404)

    account = FinancialAccount.objects.filter(account_type=FinancialAccount.AccountType.EXPENSE).first()
    category = TransactionCategory.objects.filter(category_type=TransactionCategory.CategoryType.EXPENSE).first()

    if not account:
        return JsonResponse({'error': 'حساب هزینه‌ای یافت نشد.'}, status=500)

    try:
        tx = TransactionService.create(
            reservation=reservation,
            transaction_type=transaction_type,
            amount=amount,
            created_by=request.user,
            account=account,
            category=category,
            payment_method=payment_method,
            payment_reference=external_reference,
            description=note or 'ثبت هزینه دستی',
        )
        return JsonResponse({'result': 'ok', 'transaction_id': tx.pk, 'message': 'هزینه ثبت شد.'})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=400)


@method_decorator(login_required, name='dispatch')
class PaymentEntryView(TemplateView):
    template_name = 'financial/payment_entry.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'ثبت پرداخت'
        context['form'] = TransactionForm()
        context['accounts'] = FinancialAccount.objects.filter(is_active=True)
        context['categories'] = TransactionCategory.objects.all()
        return context


@method_decorator(login_required, name='dispatch')
class ReportsView(TemplateView):
    template_name = 'financial/reports.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = {
            'date_from': self.request.GET.get('date_from'),
            'date_to': self.request.GET.get('date_to'),
            'seller_id': self.request.GET.get('seller'),
            'ledger_mode': self.request.GET.get('ledger', None),
        }
        financial_ctx = DashboardService.get_financial_context(filters=params)
        context['page_title'] = 'گزارشات مالی'
        context['totals'] = financial_ctx.get('totals', {})
        context['payment_stats'] = financial_ctx.get('payment_stats', {})
        context['chart_labels'] = financial_ctx.get('chart_labels', [])
        context['revenue_data'] = financial_ctx.get('revenue_data', [])
        context['expense_data'] = financial_ctx.get('expense_data', [])
        context['recent_transactions'] = financial_ctx.get('recent_transactions', [])
        context['upcoming_payments'] = financial_ctx.get('upcoming_payments', [])
        return context


@login_required
def export_financial_excel(request):
    params = {
        'date_from': request.GET.get('date_from'),
        'date_to': request.GET.get('date_to'),
        'seller_id': request.GET.get('seller'),
        'ledger_mode': request.GET.get('ledger', None),
    }
    variant = request.GET.get('variant', 'management')

    output = FinancialExportService.build_workbook(filters=params, variant=variant)

    response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="financial_export.xlsx"'
    return response


# Keep backwards compatibility for any older references to export_financial_csv
export_financial_csv = export_financial_excel
