#customers/vews.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView
from django.core.exceptions import PermissionDenied
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["can_create_customer"] = self.can_create_customer(user)
        context["can_edit_customer"] = self.can_edit_customer(user)
        context["can_delete_customer"] = self.can_delete_customer(user)
        context["create_form"] = CustomerForm()
        return context

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
        customer.delete()

        messages.success(request, f"مشتری «{customer_name}» با موفقیت حذف شد.")
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
