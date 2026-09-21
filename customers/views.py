#customers/vews.py
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Case, CharField, Exists, F, OuterRef, Q, Subquery, Value, When
from django.db.models.functions import Coalesce
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView
from openpyxl import Workbook
from core.ajax_forms import AjaxFormMixin
from .permissions import (
    user_can_create_customer,
    user_can_edit_customer,
    user_can_delete_customer,
)
from .models import Customer
from .forms import CustomerForm
from core.pagination import build_pagination_items, build_pagination_url
from core.search import build_token_search_query


CRM_ONLY = 'CRM_ONLY'
HAS_RESERVATION = 'HAS_RESERVATION'
HAS_CONTRACT = 'HAS_CONTRACT'
COMPLETED = 'COMPLETED'
CANCELLED = 'CANCELLED'

CRM_STATUS_LABELS = {
    CRM_ONLY: 'فقط ثبت اطلاعات در CRM',
    HAS_RESERVATION: 'دارای رزرو',
    HAS_CONTRACT: 'دارای قرارداد اجاره',
    COMPLETED: 'پایان‌یافته',
    CANCELLED: 'لغوشده',
}
CRM_STATUS_FILTERS = tuple(CRM_STATUS_LABELS.items())


class CustomerListView(LoginRequiredMixin, ListView):
    model = Customer
    template_name = "customers/list.html"
    context_object_name = "customers"
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        from reservations.constants import ReservationStatus
        from reservations.models import Reservation

        reservations = Reservation.objects.filter(customer_id=OuterRef('pk'))
        active_reservations = reservations.filter(
            status__in=[
                ReservationStatus.DRAFT,
                ReservationStatus.CONFIRMED,
                ReservationStatus.DELIVERED,
                ReservationStatus.LAUNDRY,
            ]
        )
        contractual_reservations = active_reservations.exclude(
            Q(contract_number__isnull=True) | Q(contract_number='')
        )
        completed_reservations = reservations.filter(
            status__in=[
                ReservationStatus.RETURNED,
                ReservationStatus.READY,
                ReservationStatus.ARCHIVED,
            ]
        )
        cancelled_reservations = reservations.filter(status=ReservationStatus.CANCELLED)
        latest_reservation_activity = reservations.order_by('-updated_at', '-pk').values('updated_at')[:1]

        queryset = queryset.annotate(
            has_reservation=Exists(active_reservations),
            has_contract=Exists(contractual_reservations),
            has_completed_reservation=Exists(completed_reservations),
            has_cancelled_reservation=Exists(cancelled_reservations),
            latest_reservation_activity=Subquery(latest_reservation_activity),
        ).annotate(
            crm_status=Case(
                When(has_contract=True, then=Value(HAS_CONTRACT)),
                When(has_reservation=True, then=Value(HAS_RESERVATION)),
                When(has_completed_reservation=True, then=Value(COMPLETED)),
                When(has_cancelled_reservation=True, then=Value(CANCELLED)),
                default=Value(CRM_ONLY),
                output_field=CharField(),
            ),
            last_activity_at=Coalesce(
                'latest_reservation_activity',
                F('created_at'),
            ),
        )
        search_query = self.request.GET.get('search', '').strip()
        show_with_reservations = self.request.GET.get('show_with_reservations') == '1'
        crm_status = self.request.GET.get('crm_status', '').strip()
        sort_field = self.request.GET.get('sort', 'id')
        order = self.request.GET.get('order', 'desc')

        if search_query:
            queryset = queryset.filter(build_token_search_query(
                search_query,
                (
                    'bride_first_name', 'bride_last_name', 'bride_phone',
                    'groom_first_name', 'groom_last_name',
                ),
            )
            )

        if show_with_reservations:
            from reservations.services.availability_service import ReservationAvailabilityService

            blocking_statuses = ReservationAvailabilityService.get_blocking_statuses()
            reserved_customer_ids = Reservation.objects.filter(
                customer_id__in=queryset.values_list('id', flat=True),
                status__in=blocking_statuses,
            ).values('customer_id')
            queryset = queryset.filter(id__in=reserved_customer_ids)

        if crm_status in CRM_STATUS_LABELS:
            queryset = queryset.filter(crm_status=crm_status)

        allowed_sort_fields = {
            'id': 'id',
            'bride_first_name': 'bride_first_name',
            'bride_phone': 'bride_phone',
            'ceremony_date': 'ceremony_date',
            'created_at': 'created_at',
            'last_activity': 'last_activity_at',
        }
        sort_field = allowed_sort_fields.get(sort_field, 'id')
        ordering = sort_field if order == 'asc' else f'-{sort_field}'
        return queryset.order_by(ordering)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["can_create_customer"] = self.can_create_customer(user)
        context["can_edit_customer"] = self.can_edit_customer(user)
        context["can_delete_customer"] = self.can_delete_customer(user)
        context["create_form"] = CustomerForm()
        context["search_query"] = self.request.GET.get('search', '')
        context["show_with_reservations"] = self.request.GET.get('show_with_reservations') == '1'
        context["crm_status"] = self.request.GET.get('crm_status', '')
        context["crm_status_filters"] = CRM_STATUS_FILTERS
        context["selected_crm_status_label"] = CRM_STATUS_LABELS.get(context["crm_status"], '')
        context["sort"] = self.request.GET.get('sort', 'id')
        context["order"] = self.request.GET.get('order', 'desc')
        context["crm_status_labels"] = CRM_STATUS_LABELS
        context["pagination_items"] = build_pagination_items(context['page_obj'], context['paginator'], self.request)
        context["prev_page_url"] = build_pagination_url(self.request, context['page_obj'].previous_page_number) if context['page_obj'].has_previous else None
        context["next_page_url"] = build_pagination_url(self.request, context['page_obj'].next_page_number) if context['page_obj'].has_next else None
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get('ajax') == '1' or self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return self.response_class(
                request=self.request,
                template='customers/partials/_list_results.html',
                context=context,
                **response_kwargs
            )
        return super().render_to_response(context, **response_kwargs)

    def can_create_customer(self, user):
        if user.is_superuser:
            return True
        return getattr(user, "role", None) in ["SELLER", "MANAGER", "SUPER_ADMIN"]

    def can_edit_customer(self, user):
        if user.is_superuser:
            return True
        return getattr(user, "role", None) in ["MANAGER", "SUPER_ADMIN"]

    def can_delete_customer(self, user):
        if user.is_superuser:
            return True
        return getattr(user, "role", None) in ["MANAGER", "SUPER_ADMIN"]


def export_customers_excel(request):
    queryset = Customer.objects.all()

    search_query = request.GET.get('search', '').strip()
    if search_query:
        queryset = queryset.filter(build_token_search_query(
            search_query,
            (
                'bride_first_name', 'bride_last_name', 'bride_phone',
                'groom_first_name', 'groom_last_name',
            ),
        ))

    show_with_reservations = request.GET.get('show_with_reservations') == '1'
    if show_with_reservations:
        from reservations.constants import ReservationStatus
        from reservations.models import Reservation
        from reservations.services.availability_service import ReservationAvailabilityService

        blocking_statuses = ReservationAvailabilityService.get_blocking_statuses()
        reserved_customer_ids = Reservation.objects.filter(
            customer_id__in=queryset.values_list('id', flat=True),
            status__in=blocking_statuses,
        ).values('customer_id')
        queryset = queryset.filter(id__in=reserved_customer_ids)

    crm_status = request.GET.get('crm_status', '').strip()
    if crm_status in CRM_STATUS_LABELS:
        queryset = queryset.filter(
            id__in=Customer.objects.filter(
                id__in=queryset.values_list('id', flat=True)
            ).annotate(
                crm_status=Case(
                    When(Exists(Reservation.objects.filter(customer_id=OuterRef('pk'), status__in=[
                        ReservationStatus.DRAFT,
                        ReservationStatus.CONFIRMED,
                        ReservationStatus.DELIVERED,
                        ReservationStatus.LAUNDRY,
                    ], contract_number__isnull=False).exclude(contract_number='')), then=Value(HAS_CONTRACT)),
                    When(Exists(Reservation.objects.filter(customer_id=OuterRef('pk'), status__in=[
                        ReservationStatus.DRAFT,
                        ReservationStatus.CONFIRMED,
                        ReservationStatus.DELIVERED,
                        ReservationStatus.LAUNDRY,
                    ])), then=Value(HAS_RESERVATION)),
                    When(Exists(Reservation.objects.filter(customer_id=OuterRef('pk'), status__in=[
                        ReservationStatus.RETURNED,
                        ReservationStatus.READY,
                        ReservationStatus.ARCHIVED,
                    ])), then=Value(COMPLETED)),
                    When(Exists(Reservation.objects.filter(customer_id=OuterRef('pk'), status=ReservationStatus.CANCELLED)), then=Value(CANCELLED)),
                    default=Value(CRM_ONLY),
                    output_field=CharField(),
                )
            ).filter(crm_status=crm_status).values_list('id', flat=True)
        )

    sort_field = request.GET.get('sort', 'id')
    order = request.GET.get('order', 'desc')
    allowed_sort_fields = {
        'id': 'id',
        'bride_first_name': 'bride_first_name',
        'bride_phone': 'bride_phone',
        'ceremony_date': 'ceremony_date',
        'created_at': 'created_at',
        'last_activity': 'created_at',
    }
    sort_field = allowed_sort_fields.get(sort_field, 'id')
    ordering = sort_field if order == 'asc' else f'-{sort_field}'
    queryset = queryset.order_by(ordering)

    wb = Workbook()
    ws = wb.active
    ws.title = 'مشتریان'
    headers = ['شناسه', 'نام عروس', 'نام خانوادگی عروس', 'شماره تماس عروس', 'نام داماد', 'نام خانوادگی داماد', 'شماره تماس داماد', 'تاریخ مراسم', 'تاریخ ثبت', 'وضعیت CRM']
    ws.append(headers)

    for customer in queryset:
        ws.append([
            customer.id,
            customer.bride_first_name,
            customer.bride_last_name,
            customer.bride_phone,
            customer.groom_first_name,
            customer.groom_last_name,
            customer.groom_phone,
            customer.ceremony_date.strftime('%Y/%m/%d') if customer.ceremony_date else '',
            customer.created_at.strftime('%Y/%m/%d %H:%M:%S') if customer.created_at else '',
            CRM_STATUS_LABELS.get(getattr(customer, 'crm_status', CRM_ONLY), CRM_STATUS_LABELS.get(CRM_ONLY, '')),
        ])

    for cell in ws[1]:
        cell.font = cell.font.copy(bold=True)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="customers_export.xlsx"'
    return response


class CustomerCreateView(AjaxFormMixin, LoginRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = "customers/list.html"

    ajax_success_message = "مشتری جدید با موفقیت ثبت شد."

    def dispatch(self, request, *args, **kwargs):
        if not user_can_create_customer(request.user):
            raise PermissionDenied("شما دسترسی افزودن مشتری را ندارید.")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        customer = form.save(commit=False)
        customer.created_by = self.request.user
        customer.save()
        messages.success(self.request, "مشتری جدید با موفقیت ثبت شد.")
        if self.is_ajax_form_request():
            return JsonResponse({"success": True, "message": self.ajax_success_message})
        return redirect("customers:list")

    def form_invalid(self, form):
        # پیش‌تر این متد فقط ریدایرکت می‌کرد و تمام خطاهای فیلد‌به‌فیلد
        # دور ریخته می‌شد. حالا برای درخواست‌های AJAX خطاها به‌صورت JSON
        # برگردانده می‌شوند تا مودال باز بماند و مقادیر کاربر حفظ شود.
        if self.is_ajax_form_request():
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
        messages.error(self.request, "ثبت مشتری انجام نشد. لطفاً فرم را بررسی کنید.")
        return redirect("customers:list")


class CustomerUpdateView(AjaxFormMixin, LoginRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = "customers/list.html"
    context_object_name = "customer"

    ajax_success_message = "اطلاعات مشتری با موفقیت ویرایش شد."

    def dispatch(self, request, *args, **kwargs):
        if not user_can_edit_customer(request.user):
            raise PermissionDenied("شما دسترسی ویرایش مشتری را ندارید.")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "اطلاعات مشتری با موفقیت ویرایش شد.")
        if self.is_ajax_form_request():
            return JsonResponse({"success": True, "message": self.ajax_success_message})
        return redirect("customers:list")

    def form_invalid(self, form):
        # مثل نمای ایجاد: خطاها باید به کاربر نمایش داده شوند، نه دور ریخته.
        if self.is_ajax_form_request():
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
        messages.error(self.request, "ویرایش مشتری انجام نشد. لطفاً فرم را بررسی کنید.")
        return redirect("customers:list")


class CustomerDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        if not user_can_delete_customer(request.user):
            raise PermissionDenied("شما دسترسی حذف مشتری را ندارید.")

        customer = get_object_or_404(Customer, pk=pk)
        customer_name = f"{customer.bride_first_name} {customer.bride_last_name}"

        try:
            customer.delete()
        except ProtectedError:
            messages.error(
                request,
                f"امکان حذف مشتری «{customer_name}» وجود ندارد زیرا این مشتری در رزروهای ثبت‌شده استفاده شده است."
            )
            return redirect("customers:list")

        messages.success(request, f"مشتری «{customer_name}» با موفقیت حذف شد.")
        return redirect("customers:list")


class CustomerBulkDeleteView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        if not user_can_delete_customer(request.user):
            raise PermissionDenied("شما دسترسی حذف مشتری را ندارید.")

        selected_ids = request.POST.getlist('customer_ids')
        if not selected_ids:
            messages.error(request, "هیچ مشتری‌ای برای حذف انتخاب نشده است.")
            return redirect("customers:list")

        customers = Customer.objects.filter(pk__in=selected_ids)
        deleted_count = 0
        blocked_names = []

        for customer in customers:
            try:
                customer.delete()
                deleted_count += 1
            except ProtectedError:
                blocked_names.append(f"{customer.bride_first_name} {customer.bride_last_name}")

        if deleted_count:
            messages.success(request, f"{deleted_count} مشتری با موفقیت حذف شدند.")
        if blocked_names:
            messages.error(
                request,
                "امکان حذف برخی مشتری‌ها وجود ندارد زیرا رزرو فعال یا ثبت‌شده برای آنها موجود است: " + ", ".join(blocked_names)
            )

        return redirect("customers:list")


# from django.views.generic import ListView, DetailView, TemplateView
# from .models import Customer


# class CustomerListView(ListView):
#     model = Customer
#     template_name = 'customers/list.html'
#     context_object_name = 'customers'
#     paginate_by = 20
#     ordering = ['-id']

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context['page_title'] = 'مشتریان'
#         return context


# class CustomerDetailView(DetailView):
#     model = Customer
#     template_name = 'customers/detail.html'
#     context_object_name = 'customer'

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context['page_title'] = 'جزئیات مشتری'
#         return context


# class CustomerCreateView(TemplateView):
#     template_name = 'customers/form.html'

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context['page_title'] = 'افزودن مشتری'
#         context['form_mode'] = 'create'
#         return context


# class CustomerUpdateView(TemplateView):
#     template_name = 'customers/form.html'

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context['page_title'] = 'ویرایش مشتری'
#         context['form_mode'] = 'update'
#         return context
