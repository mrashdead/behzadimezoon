from django.test import SimpleTestCase
from django.test.client import RequestFactory

from core.pagination import build_pagination_items, build_pagination_url


class PaginationTemplateTests(SimpleTestCase):
    def test_compact_pagination_renders_ellipsis_and_current_page(self):
        class DummyPage:
            number = 6
            has_previous = True
            has_next = True
            previous_page_number = 5
            next_page_number = 7

        class DummyPaginator:
            num_pages = 12

        items = build_pagination_items(DummyPage(), DummyPaginator())

        labels = [item['label'] for item in items]

        self.assertEqual(labels, ['1', '...', '6', '...', '12'])
        self.assertTrue(any(item['is_current'] for item in items))

    def test_pagination_url_preserves_existing_query_string(self):
        request = RequestFactory().get('/customers/', {'search': 'abc', 'sort': 'id', 'order': 'desc', 'page': 6})
        url = build_pagination_url(request, 7)

        self.assertIn('page=7', url)
        self.assertIn('search=abc', url)

    def test_pagination_url_accepts_callable_page_numbers(self):
        class DummyPage:
            def previous_page_number(self):
                return 5

        request = RequestFactory().get('/products/', {'search': 'abc'})
        url = build_pagination_url(request, DummyPage().previous_page_number)

        self.assertIn('page=5', url)
        self.assertIn('search=abc', url)
