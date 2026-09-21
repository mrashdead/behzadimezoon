"""رگرسیون «خلاصهٔ مالی رزرو» — ``financial/partials/_reservation_financial.html``.

انگیزهٔ ساخت این تست‌ها
----------------------
این partial با ``fetch`` داخل یک مودال تزریق می‌شود، نه با یک درخواست صفحهٔ
معمولی. همین موضوع باعث می‌شود چند قید نامرئی داشته باشد که شکستنشان هیچ
خطایی تولید نمی‌کند و فقط در مرورگر به‌شکل «دکمه‌ای که کار نمی‌کند» یا
«مودالی که باز نمی‌شود» دیده می‌شود:

۱. **ریشهٔ قالب باید ``card`` باشد.** تابع ``refreshFinancialPartial`` با
   ``temp.querySelector('.card')`` اولین کارت را برمی‌دارد و آن را جای گرهٔ
   ``[data-financial-url]`` می‌گذارد. اگر ریشه کارت نباشد، یک کارت *داخلی*
   جای کل قالب را می‌گیرد و صفحه از هم می‌پاشد.

۲. **مودال‌ها باید داخل کارت ریشه باشند.** ``fetchHtmlInto`` در
   ``finance_helpers.js`` فقط ``.card`` را برمی‌دارد و بقیهٔ fragment را دور
   می‌ریزد؛ مودال بیرون از کارت = دکمه‌هایی که هیچ کاری نمی‌کنند.

۳. **گزینه‌های روش پرداخت باید با ``PaymentMethod.CHOICES`` بخوانند.**
   پیش‌تر در فرم بازگشت وجه گزینه‌های ``CARD`` و ``CHECK`` هم بودند که در
   ``TransactionForm`` معتبر نیستند؛ انتخابشان خطای «مقدار معتبر نیست»
   می‌داد.

۴. **دکمه‌های غیرفعال نباید ``style`` درون‌خطی داشته باشند** — کلاس
   ``temporarily-disabled-action`` جای آن‌ها را گرفته است.
"""

import re
from html.parser import HTMLParser

import jdatetime
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer
from products.models import Dress
from reservations.constants import PaymentMethod
from reservations.models import Reservation

User = get_user_model()


# ---------------------------------------------------------------------------
# ابزار پیمایش HTML
# ---------------------------------------------------------------------------
class _SubtreeFinder(HTMLParser):
    """آیا شناسه‌های موردنظر *داخل* عنصری با صفت نشانه قرار دارند؟

    عمداً از یک پارسر واقعی استفاده می‌شود؛ مقایسهٔ ایندکس رشته‌ای با
    ``<div>``های تودرتو شکننده است.
    """

    VOID = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }

    def __init__(self, marker_attr, wanted_ids):
        super().__init__(convert_charrefs=True)
        self.marker_attr = marker_attr
        self.wanted = set(wanted_ids)
        self.found = set()
        self.classes_inside = set()
        self.inside = False
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if not self.inside and self.marker_attr in attrs:
            self.inside = True
            self.depth = 0
            return
        if self.inside:
            if attrs.get("id") in self.wanted:
                self.found.add(attrs["id"])
            self.classes_inside.update((attrs.get("class") or "").split())
            if tag not in self.VOID:
                self.depth += 1

    def handle_startendtag(self, tag, attrs):
        if self.inside:
            attrs = dict(attrs)
            if attrs.get("id") in self.wanted:
                self.found.add(attrs["id"])
            self.classes_inside.update((attrs.get("class") or "").split())

    def handle_endtag(self, tag):
        if self.inside and tag not in self.VOID:
            if self.depth == 0:
                self.inside = False
            else:
                self.depth -= 1


def first_card_tag(html):
    """تگ بازکنندهٔ اولین عنصری که کلاس ``card`` دارد."""
    match = re.search(r'<[a-z]+[^>]*\bclass="[^"]*\bcard\b[^"]*"[^>]*>', html)
    return match.group(0) if match else ""


def kpi_value(html, label):
    """مقدار ``data-value`` کارت شاخصی که برچسبش ``label`` است."""
    pattern = (
        r"kpi-card__label[^>]*>\s*" + re.escape(label) + r'\s*</p>.*?data-value="(-?\d+)"'
    )
    match = re.search(pattern, html, re.S)
    return int(match.group(1)) if match else None


class ReservationFinancialPartialTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="fin-partial-admin", email="fpa@example.com", password="x"
        )
        cls.dress = Dress.objects.create(code="FP-1", daily_rent_price=500000)
        cls.customer = Customer.objects.create(
            bride_first_name="نسترن",
            bride_last_name="سلطانی",
            bride_phone="09121111111",
            ceremony_date=jdatetime.date(1405, 5, 10),
        )

    def setUp(self):
        self.client.force_login(self.user)
        self._seq = 0
        self.reservation = self._reservation()
        self.url = reverse("financial:reservation_financial", args=[self.reservation.pk])

    def _reservation(self, **kwargs):
        self._seq += 1
        defaults = dict(
            customer=self.customer,
            dress=self.dress,
            contract_number=f"FP-C-{self._seq}",
            start_date=jdatetime.date(1405, 1, 1),
            rental_days=3,
            rent_price=500000,
            final_price=1500000,
            remaining_amount=1500000,
            deposit_amount=0,
            payment_method="CASH",
            payment_tracking_code=f"FPTRK-{self._seq}",
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

    def _html(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        return response.content.decode("utf-8")

    # ------------------------------------------------------------------ قید ۱
    def test_root_element_is_a_card_carrying_the_anchor_attribute(self):
        """اولین عنصر با کلاس ``card`` باید همان گرهٔ ``data-financial-url`` باشد."""
        html = self._html()
        tag = first_card_tag(html)
        self.assertTrue(tag, "هیچ عنصری با کلاس card پیدا نشد.")
        self.assertIn(
            "data-financial-url",
            tag,
            "اولین کارت قالب، گرهٔ data-financial-url نیست؛ "
            "refreshFinancialPartial یک کارت داخلی را جای کل قالب می‌گذارد.",
        )

    def test_root_card_wraps_the_modals(self):
        """مودال‌ها باید داخل کارت ریشه باشند تا با fetch از دست نروند."""
        html = self._html()
        finder = _SubtreeFinder(
            marker_attr="data-financial-url",
            wanted_ids=[
                "damageModal",
                "damageForm",
                "refundModal",
                "refundForm",
                "penaltyPaymentModal",
                "penaltyPaymentForm",
                "penaltyType",
                "penaltyAmount",
            ],
        )
        finder.feed(html)

        missing = sorted(finder.wanted - finder.found)
        self.assertEqual(
            missing,
            [],
            f"این شناسه‌ها بیرون از کارت ریشه‌اند و بعد از fetch از دست می‌روند: {missing}",
        )

    def _cancelled_reservation(self):
        """رزروی که همهٔ سه دکمهٔ مودال را فعال می‌کند.

        دکمه‌های «ثبت خسارت» و «ثبت بازگشت وجه» فقط داخل شرط ``cancellation``
        رندر می‌شوند و دکمه‌های پرداخت جریمه به ``cancellation_fee`` و
        ``damage_amount`` بزرگ‌تر از صفر وابسته‌اند.
        """
        from financial.models import CancellationRecord

        reservation = self._reservation(
            status="CANCELLED",
            cancellation_fee=200000,
            cancellation_fee_paid_amount=0,
            damage_amount=100000,
            damage_fee_paid_amount=0,
        )
        CancellationRecord.objects.create(
            reservation=reservation,
            reason="انصراف مشتری",
            penalty_amount=200000,
            refund_amount=0,
        )
        return reservation

    def _html_for(self, reservation):
        response = self.client.get(
            reverse("financial:reservation_financial", args=[reservation.pk])
        )
        self.assertEqual(response.status_code, 200)
        return response.content.decode("utf-8")

    def test_root_card_wraps_the_action_buttons(self):
        """دکمه‌های مودال باید داخل کارت ریشه باشند."""
        html = self._html_for(self._cancelled_reservation())
        finder = _SubtreeFinder(marker_attr="data-financial-url", wanted_ids=[])
        finder.feed(html)
        for cls in ("open-damage-form", "open-refund-form", "open-penalty-form"):
            self.assertIn(
                cls,
                finder.classes_inside,
                f"کلاس {cls} بیرون از کارت ریشه است.",
            )

    # ------------------------------------------------------------------ قید ۴
    def test_disabled_actions_use_class_not_inline_style(self):
        """دکمهٔ غیرفعال باید کلاس داشته باشد، نه ``style`` درون‌خطی."""
        body = self._html_for(self._cancelled_reservation())
        self.assertIn("temporarily-disabled-action", body)

        for button in re.findall(r"<button[^>]*temporarily-disabled-action[^>]*>", body):
            self.assertNotIn(
                "style=",
                button,
                "استایل درون‌خطی روی دکمهٔ غیرفعال مانده است؛ "
                "کلاس temporarily-disabled-action را استفاده کنید.",
            )

    # ------------------------------------------------------------------ قید ۳
    def test_refund_method_options_are_valid_form_choices(self):
        """گزینه‌های روش پرداخت بازگشت وجه باید زیرمجموعهٔ CHOICES باشند."""
        html = self._html()
        select = re.search(
            r'<select[^>]*name="payment_method"[^>]*>(.*?)</select>', html, re.S
        )
        self.assertIsNotNone(select, "فیلد payment_method پیدا نشد.")

        values = set(re.findall(r'<option value="([^"]*)"', select.group(1)))
        values.discard("")
        allowed = {value for value, _ in PaymentMethod.CHOICES}
        self.assertTrue(
            values <= allowed,
            f"گزینه‌های نامعتبر در فرم بازگشت وجه: {sorted(values - allowed)} "
            f"(مجاز: {sorted(allowed)})",
        )

    def test_penalty_method_options_are_valid_form_choices(self):
        html = self._html()
        select = re.search(
            r'<select[^>]*name="penalty_payment_method"[^>]*>(.*?)</select>', html, re.S
        )
        self.assertIsNotNone(select, "فیلد penalty_payment_method پیدا نشد.")
        values = set(re.findall(r'<option value="([^"]*)"', select.group(1)))
        values.discard("")
        allowed = {value for value, _ in PaymentMethod.CHOICES}
        self.assertTrue(values <= allowed, f"گزینه‌های نامعتبر: {sorted(values - allowed)}")

    # ------------------------------------------------------------------ قرارداد فیلدها
    def test_form_field_names_match_the_views(self):
        """``name`` فیلدها باید همان کلیدهایی باشند که ویوها خطا با آن‌ها می‌فرستند."""
        html = self._html()
        expected = {
            # add_damage_view ← DamageForm
            "damage_type", "amount", "payment_reference", "description",
            # create_transaction_view ← TransactionForm
            "type", "external_reference", "note",
            # reservation_record_penalty_payment ← PenaltyPaymentForm
            "penalty_type", "penalty_amount",
            "penalty_payment_method", "penalty_payment_tracking_code",
        }
        names = set(re.findall(r'name="([^"]+)"', html))
        missing = sorted(expected - names)
        self.assertEqual(missing, [], f"این نام‌های فیلد در قالب نیستند: {missing}")

    def test_modal_forms_are_novalidate(self):
        """اعتبارسنجی سمت سرور باید پیام فارسی بدهد، نه مرورگر."""
        html = self._html()
        for form_id in ("damageForm", "refundForm", "penaltyPaymentForm"):
            tag = re.search(r'<form[^>]*id="%s"[^>]*>' % form_id, html)
            self.assertIsNotNone(tag, f"فرم {form_id} پیدا نشد.")
            self.assertIn(
                "novalidate",
                tag.group(0),
                f"فرم {form_id} بدون novalidate است؛ پیام خطای مرورگر جای پیام سرور را می‌گیرد.",
            )

    # ------------------------------------------------------------------ طراحی
    def test_uses_new_design_system(self):
        html = self._html()
        # کارت‌های شاخص با partial مشترک _stat_card.html
        self.assertIn("kpi-card__value", html)
        # بخش‌ها به‌جای کارت تودرتو
        self.assertIn("fin-section", html)
        self.assertIn("fin-tile", html)
        # حالت خالی استاندارد
        self.assertIn("empty-state", html)

    def test_tables_use_rounded_row_style(self):
        """جدول‌ها (وقتی داده دارند) باید کلاس ``table-row-rounded`` بگیرند."""
        from financial.models import Guarantee

        Guarantee.objects.create(
            reservation=self.reservation,
            customer=self.customer,
            tracking_code="G-TRK-9001",
            guarantee_type="چک",
            estimated_value=500000,
        )
        html = self._html()
        self.assertIn("table-row-rounded", html)
        self.assertIn("G-TRK-9001", html)
        self.assertIn("دریافت‌شده", html)

    def test_no_leftover_old_markup(self):
        """ردپای سبک قدیمی نباید بماند."""
        html = self._html()
        self.assertNotIn("shadow-sm border rounded-3", html)
        self.assertNotIn('thead class="table-light"', html)
        self.assertNotIn("<strong>", html)

    def test_summary_header_shows_identity_and_settlement(self):
        html = self._html()
        self.assertIn("خلاصهٔ مالی رزرو", html)
        self.assertIn("FP-1", html)                 # کد لباس
        self.assertIn("نسترن سلطانی", html)          # مشتری
        self.assertIn("قطعی", html)                  # get_status_display

    def test_final_price_kpi_is_wired_to_the_reservation(self):
        """کارت «قیمت نهایی» باید به ``reservation.final_price`` وصل باشد.

        توجه: مقدار در ``data-value`` به‌صورت رقم لاتین خام می‌آید و
        ``formatNumberDisplays`` در مرورگر آن را به رقم فارسی با جداکننده
        تبدیل می‌کند؛ پس در HTML سرور نباید انتظار «1,500,000» داشت.
        """
        self.reservation.refresh_from_db()
        expected = self.reservation.final_price
        self.assertGreater(expected, 0, "قیمت نهایی در fixture صفر است؛ تست بی‌معنا می‌شود.")

        html = self._html()
        self.assertEqual(kpi_value(html, "قیمت نهایی"), expected)

    def test_received_kpi_is_zero_for_a_fresh_reservation(self):
        html = self._html()
        self.assertEqual(kpi_value(html, "دریافتی تا کنون"), 0)
        self.assertEqual(kpi_value(html, "مجموع بیعانه‌ها"), 0)

    def test_remaining_kpi_matches_the_service(self):
        from reservations.services.payment_stage_service import ReservationPaymentService

        self.reservation.refresh_from_db()
        expected = ReservationPaymentService.build_financial_summary(self.reservation)[
            "remaining_amount"
        ]
        html = self._html()
        self.assertEqual(kpi_value(html, "مانده قابل پرداخت"), expected)

    def test_empty_states_are_shown_for_a_fresh_reservation(self):
        html = self._html()
        self.assertIn("پرداخت مرحله‌ای ثبت نشده است.", html)
        self.assertIn("تراکنشی ثبت نشده است.", html)
        self.assertIn("تضمینی ثبت نشده است.", html)
        self.assertIn("خسارتی ثبت نشده است.", html)

    def test_cancellation_section_reports_not_cancelled(self):
        html = self._html()
        self.assertIn("این رزرو لغو نشده است.", html)

    # ------------------------------------------------------------------ دسترسی
    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (302, 403))


class FinancialPartialScriptTests(TestCase):
    """رگرسیون اسکریپت همراه partial (باگ «دکمه‌ها بعد از اولین عملیات می‌میرند»)."""

    def _script(self):
        from django.template.loader import render_to_string

        return render_to_string("includes/scripts/financial_reservation_partial_js.html")

    def test_refresh_reexecutes_fragment_scripts(self):
        """تازه‌سازی باید اسکریپت fragment را دوباره اجرا کند.

        بدون این کار، HTML تازه دکمه‌های مودال را با خود می‌آورد ولی هیچ
        شنوندهٔ رویدادی به آن‌ها بسته نمی‌شود.
        """
        script = self._script()
        self.assertIn("runFragmentScripts", script)
        self.assertIn("runFragmentScripts(temp)", script)
        # اسکریپت باید به یک گرهٔ متصل به سند افزوده شود، وگرنه اجرا نمی‌شود.
        self.assertIn("document.body.appendChild(newScript)", script)

    def test_error_message_from_server_is_surfaced(self):
        """پیام خطای سرور (``message``) نباید قربانی شود."""
        script = self._script()
        self.assertIn("json.errors || json.error", script)
        self.assertIn("json.message ||", script)

    def test_toast_delegates_to_ui_helpers(self):
        script = self._script()
        self.assertIn("UIHelpers.showToast", script)

    def test_no_native_alert(self):
        """``window.alert`` نباید استفاده شود."""
        script = self._script()
        self.assertNotIn("window.alert", script)
