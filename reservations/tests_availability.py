# reservations/tests_availability.py
#
# تست‌های رگرسیون برای «بررسی در‌لحظه‌ای موجودی لباس»
# (endpoint: /reservations/check-availability/)
#
# تمرکز اصلی روی پارامتر ``exclude_reservation_id`` است. این پارامتر برای
# «ویرایش رزرو» اضافه شد؛ بدون آن، رزروی که در حال ویرایش است با خودش
# تداخل می‌کند و همیشه «موجود نیست» گزارش می‌شود.

import jdatetime
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer
from products.models import Dress
from reservations.constants import ReservationStatus
from reservations.models import Reservation

User = get_user_model()


class CheckAvailabilityExcludeReservationTests(TestCase):
    """بررسی موجودی در حالت ویرایش رزرو (نادیده گرفتن خودِ رزرو)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="avail-user", password="pass12345")
        cls.dress = Dress.objects.create(code="AVL-1", daily_rent_price=100000)
        cls.customer = Customer.objects.create(
            bride_first_name="سارا",
            bride_last_name="احمدی",
            bride_phone="09120000000",
            ceremony_date=jdatetime.date(1405, 1, 3),
            how_to_know="اینستاگرام",
        )
        cls.url = reverse("reservations:check_availability")

    def setUp(self):
        self.client.force_login(self.user)
        # شماره قرارداد باید یکتا باشد (full_clean روی مدل اجرا می‌شود)
        self._contract_seq = 0

    # ------------------------- helpers -------------------------

    def _reservation(self, start, days, status=ReservationStatus.CONFIRMED):
        self._contract_seq += 1
        return Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            contract_number="C-%d" % self._contract_seq,
            start_date=start,
            rental_days=days,
            rent_price=100000,
            deposit_amount=0,
            final_price=100000,
            remaining_amount=100000,
            payment_method="CASH",
            payment_tracking_code="TRK-1",
            guarantee1_type="CHECK",
            guarantee1_tracking_code="",
            status=status,
            created_by=self.user,
        )

    def _post(self, start_jalali, days, exclude_id=None, dress_id=None):
        payload = {
            "dress_id": dress_id if dress_id is not None else self.dress.id,
            "start_date": start_jalali,
            "rental_days": days,
        }
        if exclude_id is not None:
            payload["exclude_reservation_id"] = exclude_id
        return self.client.post(self.url, payload)

    # ------------------------- tests -------------------------

    def test_self_conflict_without_exclude_parameter(self):
        """بدون exclude، رزرو خودش با خودش تداخل می‌کند (رفتار قبلی)."""
        reservation = self._reservation(jdatetime.date(1405, 1, 1), 3)

        response = self._post("1405/01/02", 1)
        data = response.json()

        self.assertTrue(data["success"])
        self.assertFalse(
            data["available"],
            "بدون exclude_reservation_id باید تداخل گزارش شود.",
        )
        self.assertIsNotNone(reservation.pk)

    def test_exclude_reservation_id_ignores_self(self):
        """با exclude، همان بازه‌ی خودِ رزرو آزاد گزارش می‌شود."""
        reservation = self._reservation(jdatetime.date(1405, 1, 1), 3)

        response = self._post("1405/01/02", 1, exclude_id=reservation.pk)
        data = response.json()

        self.assertTrue(data["success"])
        self.assertTrue(
            data["available"],
            "با exclude_reservation_id نباید خودِ رزرو تداخل حساب شود.",
        )

    def test_response_contains_delivery_date(self):
        """پاسخ باید تاریخ تحویل (یک روز قبل از شروع اجاره) را هم برگرداند.

        این فیلد برای نمایش زندهٔ «این لباس چه تاریخی باید تحویل گرفته شود»
        در مودال ویرایش رزرو استفاده می‌شود.
        """
        self._reservation(jdatetime.date(1405, 1, 1), 3)

        data = self._post("1405/02/01", 2).json()

        self.assertTrue(data["success"])
        # ۱۴۰۵/۰۲/۰۱ شمسی = 2026-04-21 میلادی؛ تحویل یک روز قبل = 2026-04-20 (۱۴۰۵/۰۱/۳۱)
        self.assertEqual(data["delivery_date"], "2026-04-20")

    def test_exact_same_range_is_available_when_excluding_self(self):
        """بازهٔ دقیقاً یکسان با خودِ رزرو هم باید آزاد باشد."""
        reservation = self._reservation(jdatetime.date(1405, 1, 1), 5)

        data = self._post("1405/01/01", 5, exclude_id=reservation.pk).json()

        self.assertTrue(data["success"])
        self.assertTrue(data["available"])

    def test_other_reservation_still_blocks_when_excluding_self(self):
        """exclude نباید رزروهای دیگر را هم نادیده بگیرد."""
        target = self._reservation(jdatetime.date(1405, 1, 1), 3)
        self._reservation(jdatetime.date(1405, 1, 2), 2)  # رزرو دیگر روی همان لباس

        data = self._post("1405/01/02", 1, exclude_id=target.pk).json()

        self.assertTrue(data["success"])
        self.assertFalse(
            data["available"],
            "تداخل با رزروهای دیگر باید همچنان گزارش شود.",
        )

    def test_non_overlapping_range_is_available(self):
        """بازهٔ بدون تداخل آزاد است."""
        reservation = self._reservation(jdatetime.date(1405, 2, 1), 3)

        data = self._post("1405/01/01", 2, exclude_id=reservation.pk).json()

        self.assertTrue(data["success"])
        self.assertTrue(data["available"])

    def test_cancelled_reservation_does_not_block(self):
        """رزرو لغوشده لباس را قفل نمی‌کند."""
        self._reservation(
            jdatetime.date(1405, 1, 1), 3, status=ReservationStatus.CANCELLED
        )

        data = self._post("1405/01/02", 1).json()

        self.assertTrue(data["success"])
        self.assertTrue(data["available"])

    def test_invalid_exclude_reservation_id_does_not_crash(self):
        """مقدار نامعتبر exclude باید بی‌صدا نادیده گرفته شود، نه اینکه خطا بدهد."""
        self._reservation(jdatetime.date(1405, 1, 1), 3)

        data = self._post("1405/01/02", 1, exclude_id="not-a-number").json()

        self.assertTrue(data["success"])
        # چون exclude نامعتبر بود، تداخل با رزرو موجود باید گزارش شود
        self.assertFalse(data["available"])

    def test_end_date_is_returned_as_gregorian_iso(self):
        """تاریخ پایان باید میلادی ISO برگردد تا سمت کلاینت به شمسی تبدیل شود."""
        data = self._post("1405/01/01", 3).json()

        self.assertTrue(data["success"])
        self.assertIsNotNone(data["end_date"])
        # الگوی YYYY-MM-DD میلادی
        self.assertRegex(data["end_date"], r"^\d{4}-\d{2}-\d{2}$")
        # 1405/01/01 شمسی = 2026-03-21 میلادی، +3 روز = 2026-03-24
        self.assertEqual(data["end_date"], "2026-03-24")

    def test_missing_fields_returns_success_false(self):
        """ورودی ناقص باید پیام خطای ساختاری برگرداند."""
        response = self.client.post(self.url, {"dress_id": self.dress.id})
        data = response.json()

        self.assertFalse(data["success"])

    def test_invalid_date_returns_success_false(self):
        """تاریخ نامعتبر نباید باعث خطای ۵۰۰ شود."""
        response = self._post("not-a-date", 2)
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(data["success"])
