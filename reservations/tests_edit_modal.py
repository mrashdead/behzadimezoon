"""رگرسیون «ویرایش رزرو» — پر شدن فرم از دیتابیس و ذخیرهٔ مقادیر رندرشده.

انگیزهٔ ساخت این تست‌ها:
-----------------------
مودال «ویرایش رزرو» مقادیر را از دیتابیس پیش‌پر می‌کند و سپس همان مقادیر را
به‌صورت POST برمی‌گرداند. اگر یکی از مقادیر رندرشده برای مدل نامعتبر باشد،
کاربر با خطای اعتبارسنجی روبه‌رو می‌شود و **نمی‌تواند رزرو را ذخیره کند** —
حتی وقتی هیچ فیلدی را تغییر نداده است.

باگ واقعی که این تست‌ها از آن محافظت می‌کنند:
``ReservationFinancialService.save_reservation_financials()`` قبل از
``Reservation.save()`` یک ``full_clean()`` صریح صدا می‌زند. نرمال‌سازی
``guarantee1_type`` (رشتهٔ خالی → ``CASH``) و ``discount_type``
(رشتهٔ خالی → ``NONE``) داخل ``save()`` انجام می‌شد؛ بنابراین ``full_clean()``
زودتر منفجر می‌شد و پیام «این فیلد نمی‌تواند خالی باشد.» برگردانده می‌شد.
"""

import json

import jdatetime
from django.contrib.auth import get_user_model
from django.test import TestCase

from customers.models import Customer
from products.models import Dress
from reservations.models import Reservation
from reservations.services.payment_stage_service import ReservationPaymentService

User = get_user_model()


class ReservationEditModalPrefillTests(TestCase):
    """پر شدن خودکار فرم ویرایش از دیتابیس + پذیرش همان مقادیر در POST."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="prefill-user", email="p@example.com", password="x"
        )
        cls.dress = Dress.objects.create(code="PF-1", daily_rent_price=500000)
        cls.customer = Customer.objects.create(
            bride_first_name="سارا",
            bride_last_name="احمدی",
            bride_phone="09120000000",
            ceremony_date=jdatetime.date(1405, 5, 10),
        )

    def setUp(self):
        self.client.force_login(self.user)
        self._contract_seq = 0

    # ------------------------------------------------------------------ helpers
    def _reservation(self, **kwargs):
        self._contract_seq += 1
        defaults = dict(
            customer=self.customer,
            dress=self.dress,
            contract_number=f"PF-C-{self._contract_seq}",
            start_date=jdatetime.date(1405, 1, 1),
            rental_days=3,
            rent_price=500000,
            final_price=1500000,
            remaining_amount=1500000,
            deposit_amount=0,
            payment_method="CASH",
            payment_tracking_code="TRK-1",
            discount_type="NONE",
            discount_value=0,
            discount_amount=0,
            guarantee1_type="CASH",
            guarantee2_type=None,
            created_by=self.user,
            status="CONFIRMED",
        )
        defaults.update(kwargs)
        return Reservation.objects.create(**defaults)

    def _post_edit(self, reservation, **overrides):
        payload = {
            "contract_number": reservation.contract_number,
            "dress": str(reservation.dress_id),
            "start_date": reservation.start_date.strftime("%Y/%m/%d"),
            "rental_days": str(reservation.rental_days),
            "discount_type": reservation.discount_type,
            "discount_value": str(reservation.discount_value or 0),
            "payment_method": reservation.payment_method,
            "payment_tracking_code": reservation.payment_tracking_code,
            "guarantee1_type": reservation.guarantee1_type or "",
            "guarantee1_tracking_code": reservation.guarantee1_tracking_code or "",
            "guarantee2_type": reservation.guarantee2_type or "",
            "guarantee2_tracking_code": reservation.guarantee2_tracking_code or "",
            "payment_revision": str(
                ReservationPaymentService.payment_revision(reservation) or ""
            ),
        }
        payload.update(overrides)
        response = self.client.post(f"/reservations/{reservation.pk}/edit/", payload)
        return response, json.loads(response.content.decode())

    # ------------------------------------------------------------------- tests
    def test_untouched_modal_round_trip_succeeds(self):
        """بازکردن مودال و زدن «ذخیره تغییرات» بدون هیچ تغییری باید موفق باشد."""
        res = self._reservation()
        response, data = self._post_edit(res)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data.get("success"), data)

    def test_empty_guarantee1_type_is_accepted(self):
        """گزینهٔ «انتخاب کنید» در ضمانت اول نباید ذخیره را بشکند."""
        res = self._reservation()
        response, data = self._post_edit(res, guarantee1_type="")
        self.assertTrue(data.get("success"), data)
        res.refresh_from_db()
        # نرمال‌سازی: رشتهٔ خالی به CASH تبدیل می‌شود (سازگاری با ستون blank=False)
        self.assertEqual(res.guarantee1_type, "CASH")

    def test_empty_discount_type_is_accepted(self):
        """گزینهٔ «بدون تخفیف» با مقدار خالی هم باید ذخیره شود."""
        res = self._reservation()
        response, data = self._post_edit(res, discount_type="")
        self.assertTrue(data.get("success"), data)
        res.refresh_from_db()
        self.assertEqual(res.discount_type, "NONE")

    def test_discount_change_is_persisted(self):
        """تغییر نوع تخفیف از مودال باید در دیتابیس ذخیره شود.

        توجه: فرم ویرایش قیمت اجاره را از ``dress.daily_rent_price`` بازمحاسبه
        می‌کند (قیمت‌گذاری مجدد هنگام ویرایش)، پس مبلغ پایه همان ۵۰۰٬۰۰۰ است.
        """
        res = self._reservation()
        _, data = self._post_edit(res, discount_type="AMOUNT", discount_value="100000")
        self.assertTrue(data.get("success"), data)
        res.refresh_from_db()
        self.assertEqual(res.discount_type, "AMOUNT")
        self.assertEqual(res.discount_amount, 100000)
        self.assertEqual(res.final_price, 400000)

    def test_date_and_days_change_recalculates_end_date(self):
        """تغییر تاریخ شروع/تعداد روز از مودال باید تاریخ پایان را بازمحاسبه کند."""
        res = self._reservation()
        _, data = self._post_edit(res, start_date="1405/02/01", rental_days="5")
        self.assertTrue(data.get("success"), data)
        res.refresh_from_db()
        self.assertEqual(res.start_date, jdatetime.date(1405, 2, 1))
        self.assertEqual(res.rental_days, 5)
        self.assertEqual(res.end_date, jdatetime.date(1405, 2, 6))

    def test_modal_renders_prefilled_values(self):
        """مقادیر نمایش‌داده‌شده در HTML باید با دیتابیس یکی باشند."""
        res = self._reservation(
            contract_number="PF-RENDER-9",
            discount_type="PERCENT",
            discount_value=20,
        )
        # صفحهٔ لیست رزروها مودال‌ها را رندر می‌کند
        response = self.client.get("/reservations/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="editReservationModal', html)
        self.assertIn("PF-RENDER-9", html)
        self.assertIn("1405/01/01", html)
        self.assertIn("value=\"PERCENT\" selected", html)
