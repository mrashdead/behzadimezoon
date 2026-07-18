#dashboard/views.py
import mimetypes
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods
from django.views.generic import TemplateView
from django.db.models import Sum
from customers.models import Customer
from products.models import Dress
from reservations.constants import ReservationStatus
from reservations.utils import get_reservations_for_user
from reservations.models import Reservation
from financial.services import DashboardService
from .backup_service import (
    list_backup_files,
    resolve_backup_file_path,
    validate_backup_download_token,
)


class DashboardView(TemplateView):
    template_name = 'dashboard/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get filtered reservations based on user role
        user_reservations = get_reservations_for_user(self.request.user)

        context['customers_count'] = Customer.objects.count()
        context['dresses_count'] = Dress.objects.count()
        context['active_reservations_count'] = user_reservations.filter(
            status__in=[
                ReservationStatus.DRAFT,
                ReservationStatus.CONFIRMED,
                ReservationStatus.DELIVERED,
            ]
        ).count()

        # Financial context (transaction-first where available)
        financial_ctx = DashboardService.get_financial_context()
        context['totals'] = financial_ctx.get('totals', {})
        context['recent_transactions'] = financial_ctx.get('recent_transactions', [])
        context['uses_transaction_ledger'] = financial_ctx.get('uses_transaction_ledger', False)
        context['open_reconciliation_issues'] = financial_ctx.get('open_reconciliation_issues', 0)
        # Backwards-compatible single value used in template
        context['total_income'] = context['totals'].get('total_cash_inflow', 0)

        # Defer newly added DB columns until migrations have been applied
        context['recent_reservations'] = user_reservations.select_related(
            'customer', 'dress'
        ).defer('discount_type', 'discount_value', 'discount_amount', 'refunded_amount').order_by('-created_at')[:3]

        context['active_reservations'] = user_reservations.select_related(
            'customer', 'dress'
        ).defer('discount_type', 'discount_value', 'discount_amount', 'refunded_amount').filter(
            status__in=[
                ReservationStatus.DRAFT,
                ReservationStatus.CONFIRMED,
                ReservationStatus.DELIVERED,
            ]
        ).order_by('-created_at')[:10]

        context['page_title'] = 'داشبورد'
        return context


@login_required
@require_GET
def backup_list_view(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    backups = list_backup_files()
    return render(request, 'dashboard/backup_list.html', {'backups': backups})


@login_required
@require_http_methods(['GET', 'POST'])
def backup_download_view(request, token):
    if not request.user.is_superuser:
        raise PermissionDenied

    secret_value = getattr(settings, 'BACKUP_DOWNLOAD_SECRET', None)
    if not secret_value:
        return HttpResponseForbidden('رمز دانلود پیکربندی نشده است.')

    try:
        filename = validate_backup_download_token(token)
        backup_path = resolve_backup_file_path(filename)
    except signing.SignatureExpired:
        return HttpResponseForbidden('لینک دانلود منقضی شده است.')
    except signing.BadSignature:
        return HttpResponseForbidden('لینک دانلود نامعتبر است.')
    except (ValueError, FileNotFoundError):
        raise Http404('فایل بکاپ پیدا نشد.')

    if request.method == 'POST':
        password = request.POST.get('download_secret', '').strip()
        if password != secret_value:
            return render(
                request,
                'dashboard/backup_download_auth.html',
                {
                    'token': token,
                    'backup_name': backup_path.name,
                    'error_message': 'رمز وارد شده صحیح نیست.',
                },
            )

        content_type, _ = mimetypes.guess_type(backup_path.name)
        return FileResponse(
            open(backup_path, 'rb'),
            as_attachment=True,
            filename=backup_path.name,
            content_type=content_type or 'application/octet-stream',
        )

    return render(
        request,
        'dashboard/backup_download_auth.html',
        {'token': token, 'backup_name': backup_path.name},
    )


class TempUIView(TemplateView):
    template_name = 'dashboard/temp-ui.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'صفحه آزمایشی'
        return context


class TempFormsView(TemplateView):
    template_name = 'dashboard/temp-forms.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'صفحه آزمایشی'
        return context
