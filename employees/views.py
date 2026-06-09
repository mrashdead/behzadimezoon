#employees/views.py
from django.views.generic import TemplateView


class EmployeeListView(TemplateView):
    template_name = 'employees/list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'کارمندان'
        return context
