"""رگرسیون فرم‌های داخل مودال (AJAX) برای مشتریان و محصولات.

انگیزه
------
پیش‌تر وقتی فرم «افزودن/ویرایش مشتری» نامعتبر بود، نما فقط یک پیام کلی
نمایش می‌داد و صفحه را ریدایرکت می‌کرد؛ یعنی خطاهای فیلد‌به‌فیلد **دور
ریخته می‌شد** و کاربر داده‌های واردشده‌اش را از دست می‌داد.

اکنون با ``core.ajax_forms.AjaxFormMixin`` برای درخواست‌های AJAX خطاها
به‌صورت JSON برگردانده می‌شوند (HTTP 400) تا مودال باز بماند. این تست‌ها
هم رفتار جدید (AJAX) و هم سازگاری عقب‌رو (درخواست معمولی → ریدایرکت)
را تضمین می‌کنند.
"""

import json

import jdatetime
from django.contrib.auth import get_user_model
from django.test import TestCase

from customers.models import Customer
from products.models import Dress

User = get_user_model()

AJAX_HEADERS = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class CustomerModalAjaxFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="crm-manager", password="x", role=User.Role.MANAGER
        )
        cls.customer = Customer.objects.create(
            bride_first_name="مینا",
            bride_last_name="کریمی",
            bride_phone="09121112233",
            ceremony_date=jdatetime.date(1405, 3, 1),
        )

    def setUp(self):
        self.client.force_login(self.manager)

    # ------------------------------------------------------------------ create
    def test_create_with_invalid_data_returns_json_errors(self):
        response = self.client.post(
            "/customers/create/",
            {"bride_first_name": "", "bride_last_name": "", "bride_phone": "123"},
            **AJAX_HEADERS,
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content.decode())
        self.assertFalse(data["success"])
        self.assertIn("bride_first_name", data["errors"])
        self.assertIn("bride_phone", data["errors"])

    def test_create_with_valid_data_returns_success_json(self):
        response = self.client.post(
            "/customers/create/",
            {
                "bride_first_name": "زهرا",
                "bride_last_name": "مرادی",
                "bride_phone": "09129998877",
                "ceremony_date": "1405/04/10",
                "how_to_know": "اینستاگرام",
            },
            **AJAX_HEADERS,
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode())
        self.assertTrue(data["success"], data)
        self.assertTrue(
            Customer.objects.filter(bride_first_name="زهرا").exists()
        )

    def test_create_without_ajax_still_redirects(self):
        """سازگاری عقب‌رو: درخواست معمولی باید مثل قبل ریدایرکت شود."""
        response = self.client.post(
            "/customers/create/",
            {
                "bride_first_name": "سحر",
                "bride_last_name": "نادری",
                "bride_phone": "09121234567",
                "ceremony_date": "1405/05/05",
                "how_to_know": "تبلیغات",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/customers/")

    def test_create_invalid_without_ajax_redirects(self):
        response = self.client.post(
            "/customers/create/",
            {"bride_first_name": "", "bride_last_name": ""},
        )
        self.assertEqual(response.status_code, 302)

    # -------------------------------------------------------------------- edit
    def test_update_with_invalid_data_returns_json_errors(self):
        response = self.client.post(
            f"/customers/edit/{self.customer.pk}/",
            {
                "bride_first_name": "مینا",
                "bride_last_name": "کریمی",
                # دقیقاً ۱۱ کاراکتر ولی رقم نیست: پیش‌تر فقط طول بررسی می‌شد
                # و این مقدار از اعتبارسنجی رد می‌شد.
                "bride_phone": "notaphone11",
                "ceremony_date": "1405/03/01",
                "how_to_know": "ندارد",
            },
            **AJAX_HEADERS,
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content.decode())
        self.assertFalse(data["success"])
        self.assertIn("bride_phone", data["errors"])

    def test_update_with_short_phone_returns_error(self):
        response = self.client.post(
            f"/customers/edit/{self.customer.pk}/",
            {
                "bride_first_name": "مینا",
                "bride_last_name": "کریمی",
                "bride_phone": "12345",
                "ceremony_date": "1405/03/01",
                "how_to_know": "ندارد",
            },
            **AJAX_HEADERS,
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content.decode())
        self.assertIn("bride_phone", data["errors"])

    def test_update_with_valid_data_returns_success_json(self):
        response = self.client.post(
            f"/customers/edit/{self.customer.pk}/",
            {
                "bride_first_name": "مینا",
                "bride_last_name": "کریمی",
                "bride_phone": "09121112233",
                "ceremony_date": "1405/03/01",
                "how_to_know": "ندارد",
                "city": "تهران",
            },
            **AJAX_HEADERS,
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode())
        self.assertTrue(data["success"], data)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.city, "تهران")


class ProductModalAjaxFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="prod-manager", password="x", role=User.Role.MANAGER
        )
        cls.dress = Dress.objects.create(code="AJX-1", daily_rent_price=300000)

    def setUp(self):
        self.client.force_login(self.manager)

    def test_create_invalid_price_returns_json_errors(self):
        response = self.client.post(
            "/products/add/",
            {"code": "AJX-NEW", "daily_rent_price": "0"},
            **AJAX_HEADERS,
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content.decode())
        self.assertFalse(data["success"])
        self.assertIn("daily_rent_price", data["errors"])

    def test_create_valid_returns_success_json(self):
        response = self.client.post(
            "/products/add/",
            {"code": "AJX-NEW", "daily_rent_price": "۴۵۰,۰۰۰"},
            **AJAX_HEADERS,
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode())
        self.assertTrue(data["success"], data)
        self.assertTrue(Dress.objects.filter(code="AJX-NEW").exists())

    def test_edit_valid_returns_success_json(self):
        response = self.client.post(
            f"/products/{self.dress.pk}/edit/",
            {"code": "AJX-1", "daily_rent_price": "350000"},
            **AJAX_HEADERS,
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode())
        self.assertTrue(data["success"], data)
        self.dress.refresh_from_db()
        self.assertEqual(self.dress.daily_rent_price, 350000)

    def test_edit_duplicate_code_returns_json_errors(self):
        Dress.objects.create(code="AJX-DUP", daily_rent_price=100000)
        response = self.client.post(
            f"/products/{self.dress.pk}/edit/",
            {"code": "AJX-DUP", "daily_rent_price": "100000"},
            **AJAX_HEADERS,
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content.decode())
        self.assertFalse(data["success"])
        self.assertIn("code", data["errors"])
