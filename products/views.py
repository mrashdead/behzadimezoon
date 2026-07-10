#products/views.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import DressForm
from .models import Dress


class ProductManagerPermissionMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        user = self.request.user
        return user.is_superuser or getattr(user, 'role', None) in ['SUPER_ADMIN', 'MANAGER']


class ProductCreatePermissionMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        user = self.request.user
        return user.is_superuser or getattr(user, 'role', None) in ['SUPER_ADMIN', 'MANAGER', 'SELLER']


class DressListView(ListView):
    model = Dress
    template_name = 'products/list.html'
    context_object_name = 'dresses'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('search', '').strip()
        show_reserved_only = self.request.GET.get('show_reserved_only') == '1'
        sort_field = self.request.GET.get('sort', 'id')
        order = self.request.GET.get('order', 'desc')

        if search_query:
            queryset = queryset.filter(code__icontains=search_query)

        if show_reserved_only:
            from reservations.models import Reservation
            from reservations.services.availability_service import ReservationAvailabilityService

            blocking_statuses = ReservationAvailabilityService.get_blocking_statuses()
            reserved_ids = set(
                Reservation.objects.filter(
                    status__in=blocking_statuses,
                    dress_id__in=queryset.values_list('id', flat=True),
                ).values_list('dress_id', flat=True)
            )
            queryset = queryset.filter(id__in=reserved_ids)

        allowed_sort_fields = {
            'id': 'id',
            'code': 'code',
            'daily_rent_price': 'daily_rent_price',
            'created_at': 'created_at',
        }
        sort_field = allowed_sort_fields.get(sort_field, 'id')
        ordering = sort_field if order == 'asc' else f'-{sort_field}'
        return queryset.order_by(ordering)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'محصولات'
        context['form'] = DressForm()
        context['search_query'] = self.request.GET.get('search', '')
        context['show_reserved_only'] = self.request.GET.get('show_reserved_only') == '1'
        context['sort'] = self.request.GET.get('sort', 'id')
        context['order'] = self.request.GET.get('order', 'desc')
        user = self.request.user
        can_create_product = user.is_authenticated and (
            user.is_superuser or getattr(user, 'role', None) in ['SUPER_ADMIN', 'MANAGER', 'SELLER']
        )
        can_edit_product = user.is_authenticated and (
            user.is_superuser or getattr(user, 'role', None) in ['SUPER_ADMIN', 'MANAGER']
        )
        can_delete_product = can_edit_product
        context['can_create_product'] = can_create_product
        context['can_edit_product'] = can_edit_product
        context['can_delete_product'] = can_delete_product
        context['can_manage_product'] = can_edit_product or can_delete_product
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get('ajax') == '1' or self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return self.response_class(
                request=self.request,
                template='products/partials/_list_results.html',
                context=context,
                **response_kwargs
            )
        return super().render_to_response(context, **response_kwargs)

class DressCreateView(ProductCreatePermissionMixin, CreateView):
    model = Dress
    form_class = DressForm
    template_name = 'products/form.html'
    success_url = reverse_lazy('products:list')

    def form_valid(self, form):
        messages.success(self.request, 'محصول با موفقیت ایجاد شد.')
        return super().form_valid(form)

    def form_invalid(self, form):
        print('CREATE ERRORS:', form.errors)
        messages.error(self.request, 'لطفاً خطاهای فرم را بررسی کنید.')
        return self.render_to_response(self.get_context_data(form=form, form_mode='create'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'افزودن محصول'
        context['form_mode'] = 'create'
        return context


class DressUpdateView(ProductManagerPermissionMixin, UpdateView):
    model = Dress
    form_class = DressForm
    template_name = 'products/form.html'
    context_object_name = 'dress'
    success_url = reverse_lazy('products:list')

    def form_valid(self, form):
        messages.success(self.request, 'محصول با موفقیت ویرایش شد.')
        return super().form_valid(form)

    def form_invalid(self, form):
        print('UPDATE ERRORS:', form.errors)
        messages.error(self.request, 'لطفاً خطاهای فرم را بررسی کنید.')
        return self.render_to_response(self.get_context_data(form=form, form_mode='update'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'ویرایش محصول'
        context['form_mode'] = 'update'
        return context


class DressDeleteView(ProductManagerPermissionMixin, View):
    def post(self, request, pk):
        dress = get_object_or_404(Dress, pk=pk)
        try:
            dress.delete()
        except ProtectedError:
            messages.error(request, "امکان حذف این محصول وجود ندارد زیرا در رزروهای ثبت‌شده استفاده شده است.")
            return redirect("products:list")

        messages.success(request, "محصول با موفقیت حذف شد.")
        return redirect("products:list")


class DressBulkDeleteView(ProductManagerPermissionMixin, View):
    def post(self, request, *args, **kwargs):
        selected_ids = request.POST.getlist('dress_ids')
        if not selected_ids:
            messages.error(request, "هیچ محصولی برای حذف انتخاب نشده است.")
            return redirect("products:list")

        dresses = Dress.objects.filter(pk__in=selected_ids)
        deleted_count = 0
        blocked_codes = []

        for dress in dresses:
            try:
                dress.delete()
                deleted_count += 1
            except ProtectedError:
                blocked_codes.append(dress.code)

        if deleted_count:
            messages.success(request, f"{deleted_count} محصول با موفقیت حذف شدند.")
        if blocked_codes:
            messages.error(
                request,
                "امکان حذف برخی محصولات وجود ندارد زیرا در رزروهای فعال یا ثبت‌شده استفاده شده‌اند: " + ", ".join(blocked_codes)
            )

        return redirect("products:list")

