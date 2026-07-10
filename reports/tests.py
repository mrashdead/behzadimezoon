from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class ReportsIndexViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='report-admin',
            password='test-pass123',
            role=get_user_model().Role.MANAGER,
        )

    def test_reports_index_renders_operational_summary(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('reports:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'خلاصه عملکرد و گزارش‌های مدیریتی')
        self.assertContains(response, 'فیلتر گزارش')
        self.assertContains(response, 'روند درآمد و رزرو')

    def test_reports_filters_accept_dress_filter_without_error(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('reports:index'), {'dress_id': 999})

        self.assertEqual(response.status_code, 200)

    def test_reports_filter_inputs_use_persian_datepicker(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('reports:index'))

        self.assertContains(response, 'class="form-control form-control-sm p-date-range"')
        self.assertContains(response, 'id="dateRangeInput"')
