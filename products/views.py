from django.views.generic import ListView, DetailView, TemplateView
from .models import Dress


class DressListView(ListView):
    model = Dress
    template_name = 'products/list.html'
    context_object_name = 'dresses'
    paginate_by = 20
    ordering = ['-id']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'محصولات'
        return context


class DressDetailView(DetailView):
    model = Dress
    template_name = 'products/detail.html'
    context_object_name = 'dress'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'جزئیات محصول'
        return context


class DressCreateView(TemplateView):
    template_name = 'products/form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'افزودن محصول'
        context['form_mode'] = 'create'
        return context


class DressUpdateView(TemplateView):
    template_name = 'products/form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'ویرایش محصول'
        context['form_mode'] = 'update'
        return context
