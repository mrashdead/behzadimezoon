"""رگرسیون صفحهٔ «لیست رزروها» — کارت‌های خلاصهٔ وضعیت و فیلتر کلیک‌پذیر.

انگیزهٔ ساخت این تست‌ها:
-----------------------
صفحهٔ لیست رزروها بازنویسی شد و ۸ کارت خلاصهٔ وضعیت گرفت که هر کدام
به‌عنوان فیلتر کلیک‌پذیر عمل می‌کند. دو خطر واقعی وجود دارد:

۱. **صفر شدن کارت‌ها هنگام فیلتر:** اگر شمارش وضعیت‌ها روی مجموعهٔ
   «فیلترشده با وضعیت» انجام شود، به‌محض کلیک روی یکی از کارت‌ها بقیهٔ
   کارت‌ها صفر می‌شوند و کاربر فکر می‌کند رزروی در آن وضعیت وجود ندارد.

۲. **از دست رفتن جستجو:** کلیک روی کارت وضعیت نباید عبارت جستجوی جاری را
   پاک کند.

همچنین این تست‌ها قفل می‌کنند که کلاس ``customer-mobile-table`` روی جدول
باقی بماند؛ بدون آن صفت‌های ``data-label`` بی‌اثر می‌شوند و جدول در موبایل
سرریز می‌کند.
"""

import re

import jdatetime
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer
from products.models import Dress
from reservations.models import Reservation

User = get_user_model()


def table_rows(html):
    """تعداد ردیف‌های جدول رزروها (فقط داخل ``tbody`` همان جدول)."""
    start = html.index('id="dt_ReservationList"')
    body = html.index('<tbody>', start)
    end = html.index('</tbody>', body)
    return html[body:end].count('data-label="ردیف"')


def kpi_value(html, label):
    """مقدار ``data-value`` کارت خلاصه‌ای که برچسبش ``label`` است."""
    pattern = (
        r'kpi-card__label[^>]*>\s*' + re.escape(label) + r'\s*</p>.*?data-value="(-?\d+)"'
    )
    match = re.search(pattern, html, re.S)
    return int(match.group(1)) if match else None


class ReservationListPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="list-admin", email="la@example.com", password="x"
        )
        cls.dress = Dress.objects.create(code="LP-1", daily_rent_price=500000)
        cls.customer = Customer.objects.create(
            bride_first_name="سارا",
            bride_last_name="احمدی",
            bride_phone="09120000000",
            ceremony_date=jdatetime.date(1405, 5, 10),
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("reservations:list")
        self._seq = 0

    # ------------------------------------------------------------------ helpers
    def _reservation(self, status="CONFIRMED", **kwargs):
        self._seq += 1
        defaults = dict(
            customer=self.customer,
            dress=self.dress,
            contract_number=f"LP-C-{self._seq}",
            start_date=jdatetime.date(1405, 1, 1),
            rental_days=3,
            rent_price=500000,
            final_price=1500000,
            remaining_amount=1500000,
            deposit_amount=0,
            payment_method="CASH",
            payment_tracking_code=f"TRK-{self._seq}",
            discount_type="NONE",
            discount_value=0,
            discount_amount=0,
            guarantee1_type="CASH",
            guarantee2_type=None,
            created_by=self.user,
            status=status,
        )
        defaults.update(kwargs)
        return Reservation.objects.create(**defaults)

    def _html(self, **params):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)
        return response.content.decode("utf-8")

    # ------------------------------------------------------------------ markup
    def test_page_renders_new_design_markup(self):
        self._reservation()
        html = self._html()

        self.assertIn("page-head-card", html)
        self.assertIn("لیست رزروها", html)
        # کلاس لازم برای تبدیل جدول به کارت در موبایل
        self.assertIn("customer-mobile-table", html)
        # کارت‌های خلاصهٔ وضعیت
        self.assertIn("kpi-card", html)

    def test_layout_markup_is_balanced(self):
        self._reservation()
        html = self._html()

        self.assertEqual(html.count("<div"), html.count("</div>"))
        self.assertEqual(html.count("<table"), html.count("</table>"))
        self.assertEqual(html.count("<tr"), html.count("</tr>"))
        self.assertEqual(html.count("<form"), html.count("</form>"))

    def test_legacy_lucide_icon_replaced_with_flaticon(self):
        """``icon-eye`` از کتابخانهٔ Lucide بود و با بقیهٔ آیکون‌ها ناهمگون."""
        self._reservation()
        html = self._html()

        self.assertNotIn('class="icon-eye"', html)
        self.assertIn("fi fi-rr-eye", html)

    def test_table_responsive_contract(self):
        """جدول نباید از کارت بیرون بزند و breakpoint عملیات باید هماهنگ باشد.

        باگ واقعی: یک قانون سراسری ``overflow: visible !important`` رفتار
        ``table-responsive`` بوت‌استرپ را خنثی کرده بود. جدول با جمع حداقل
        عرض ستون‌های حدود ۱۳۸۰px مستقیماً از کارت بیرون می‌زد.
        """
        self._reservation()
        html = self._html()

        self.assertIn(
            'class="table-responsive customer-table-wrap reservation-table-wrap"',
            html,
        )
        # چون حالت کارت تا زیر 992px فعال است، دکمه‌های متعدد هم باید از lg
        # به بعد نمایش داده شوند و در تبلت منوی فشرده جای آن‌ها را بگیرد.
        self.assertIn("d-none d-lg-inline-flex", html)
        self.assertIn("dropdown d-lg-none", html)
        self.assertNotIn("d-none d-md-inline-flex", html)
        self.assertNotIn("dropdown d-md-none", html)
        self.assertNotIn('style="min-width: 180px;"', html)

    def test_table_css_keeps_overflow_inside_the_card(self):
        """قانون مخرب ``overflow: visible !important`` نباید برگردد."""
        from django.conf import settings

        css_path = settings.BASE_DIR / "static" / "assets" / "css" / "custom.css"
        css = css_path.read_text(encoding="utf-8")
        # توضیح تاریخیِ باگ در comment نگه داشته شده؛ فقط declarationهای
        # اجرایی را بررسی می‌کنیم.
        executable_css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

        self.assertNotIn("overflow: visible !important", executable_css)
        self.assertIn("@media (max-width: 991.98px)", css)
        self.assertIn(".table-responsive.customer-table-wrap", css)
        self.assertIn("overflow-x: auto", css)
        self.assertIn("overflow-wrap: anywhere", css)

    # ------------------------------------------------------------ status cards
    def test_status_cards_count_every_status(self):
        self._reservation(status="CONFIRMED")
        self._reservation(status="CONFIRMED")
        self._reservation(status="DELIVERED")
        html = self._html()

        self.assertEqual(kpi_value(html, "کل رزروها"), 3)
        self.assertEqual(kpi_value(html, "قطعی (در انتظار تحویل)"), 2)
        self.assertEqual(kpi_value(html, "تحویل به مشتری"), 1)
        self.assertEqual(kpi_value(html, "لغو شده"), 0)

    def test_status_counts_are_not_zeroed_by_active_filter(self):
        """باگ کلیدی: فیلتر وضعیت نباید بقیهٔ کارت‌ها را صفر کند."""
        self._reservation(status="CONFIRMED")
        self._reservation(status="CONFIRMED")
        self._reservation(status="DELIVERED")
        html = self._html(status="CONFIRMED")

        # جدول فیلتر شده...
        self.assertEqual(table_rows(html), 2)
        # ...ولی کارت‌ها هنوز کل تصویر را نشان می‌دهند
        self.assertEqual(kpi_value(html, "کل رزروها"), 3)
        self.assertEqual(kpi_value(html, "قطعی (در انتظار تحویل)"), 2)
        self.assertEqual(kpi_value(html, "تحویل به مشتری"), 1)

    def test_status_filter_limits_table_rows(self):
        self._reservation(status="CONFIRMED")
        self._reservation(status="CONFIRMED")
        self._reservation(status="DELIVERED")

        self.assertEqual(table_rows(self._html()), 3)
        self.assertEqual(table_rows(self._html(status="DELIVERED")), 1)
        self.assertEqual(table_rows(self._html(status="CANCELLED")), 0)

    def test_invalid_status_value_is_ignored(self):
        self._reservation(status="CONFIRMED")
        self._reservation(status="DELIVERED")
        html = self._html(status="NOT-A-REAL-STATUS")

        # نه خطا، نه فیلتر ناخواسته
        self.assertEqual(table_rows(html), 2)
        # و بنر «فیلتر فعال» نباید نمایش داده شود
        self.assertNotIn("حذف فیلتر وضعیت", html)

    def test_status_filter_is_case_insensitive(self):
        self._reservation(status="CONFIRMED")
        self._reservation(status="DELIVERED")
        self.assertEqual(table_rows(self._html(status="confirmed")), 1)

    def test_active_filter_banner_shows_clear_link(self):
        self._reservation(status="DELIVERED")
        html = self._html(status="DELIVERED")

        self.assertIn("حذف فیلتر وضعیت", html)
        self.assertIn("تحویل به مشتری", html)

    def test_status_card_link_preserves_active_search(self):
        """کلیک روی کارت وضعیت نباید جستجوی جاری را پاک کند."""
        self._reservation(status="CONFIRMED", contract_number="FIND-ME-1")
        html = self._html(search="FIND-ME-1")

        self.assertIn("status=CONFIRMED&amp;search=FIND-ME-1", html)

    def test_archived_reservations_are_excluded(self):
        self._reservation(status="CONFIRMED")
        self._reservation(status="ARCHIVED")
        html = self._html()

        self.assertEqual(table_rows(html), 1)
        # آرشیو در شمارش وضعیت‌ها هم نمی‌آید چون از ابتدا از queryset حذف شده
        self.assertEqual(kpi_value(html, "کل رزروها"), 1)

    def test_empty_state_renders_when_filter_matches_nothing(self):
        self._reservation(status="CONFIRMED")
        html = self._html(status="CANCELLED")

        self.assertEqual(table_rows(html), 0)
        self.assertIn("empty-state", html)
        self.assertIn("رزروی با این وضعیت وجود ندارد", html)
