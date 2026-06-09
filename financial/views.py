from django.views.generic import TemplateView


class FinancialListView(TemplateView):
    template_name = 'financial/list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'مالی'
        return context
