#products/views.py
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import DressForm
from .models import Dress


class DressListView(ListView):
    model = Dress
    template_name = 'products/list.html'
    context_object_name = 'dresses'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'محصولات'
        context['form'] = DressForm()
        return context

class DressCreateView(CreateView):
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


class DressUpdateView(UpdateView):
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


class DressDeleteView(View):
    def post(self, request, pk):
        dress = get_object_or_404(Dress, pk=pk)
        dress.delete()
        messages.success(request, "محصول با موفقیت حذف شد.")
        return redirect("products:list")

