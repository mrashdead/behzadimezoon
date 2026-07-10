#customers/vews.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView
from .permissions import (
    user_can_create_customer,
    user_can_edit_customer,
    user_can_delete_customer,
)
from .models import Customer
from .forms import CustomerForm


class CustomerListView(LoginRequiredMixin, ListView):
    model = Customer
    template_name = "customers/list.html"
    context_object_name = "customers"
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('search', '').strip()
        show_with_reservations = self.request.GET.get('show_with_reservations') == '1'
        sort_field = self.request.GET.get('sort', 'id')
        order = self.request.GET.get('order', 'desc')

        if search_query:
            queryset = queryset.filter(
                Q(bride_first_name__icontains=search_query) |
                Q(bride_last_name__icontains=search_query) |
                Q(bride_phone__icontains=search_query) |
                Q(groom_first_name__icontains=search_query) |
                Q(groom_last_name__icontains=search_query)
            )

        if show_with_reservations:
            from reservations.models import Reservation
            from reservations.services.availability_service import ReservationAvailabilityService

            blocking_statuses = ReservationAvailabilityService.get_blocking_statuses()
            reserved_customer_ids = set(
                Reservation.objects.filter(
                    customer_id__in=queryset.values_list('id', flat=True),
                    status__in=blocking_statuses,
                ).values_list('customer_id', flat=True)
            )
            queryset = queryset.filter(id__in=reserved_customer_ids)

        allowed_sort_fields = {
            'id': 'id',
            'bride_first_name': 'bride_first_name',
            'bride_phone': 'bride_phone',
            'ceremony_date': 'ceremony_date',
            'created_at': 'created_at',
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
        context["sort"] = self.request.GET.get('sort', 'id')
        context["order"] = self.request.GET.get('order', 'desc')
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


class CustomerCreateView(LoginRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = "customers/list.html"

    def dispatch(self, request, *args, **kwargs):
        if not user_can_create_customer(request.user):
            raise PermissionDenied("شما دسترسی افزودن مشتری را ندارید.")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        customer = form.save(commit=False)
        customer.created_by = self.request.user
        customer.save()
        messages.success(self.request, "مشتری جدید با موفقیت ثبت شد.")
        return redirect("customers:list")

    def form_invalid(self, form):
        print("CREATE ERRORS:", form.errors)
        messages.error(self.request, "ثبت مشتری انجام نشد. لطفاً فرم را بررسی کنید.")
        return redirect("customers:list")


class CustomerUpdateView(LoginRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = "customers/list.html"
    context_object_name = "customer"

    def dispatch(self, request, *args, **kwargs):
        if not user_can_edit_customer(request.user):
            raise PermissionDenied("شما دسترسی ویرایش مشتری را ندارید.")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "اطلاعات مشتری با موفقیت ویرایش شد.")
        return redirect("customers:list")

    def form_invalid(self, form):
        print("UPDATE ERRORS:", form.errors)
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
