"""Smoke tests برای قالب‌ها — جلوگیری از بازگشت باگ‌های سراسری قالب.

این تست‌ها سه دسته خطا را می‌گیرند که پیش‌تر واقعاً رخ داده بودند:

۱. **خطای نگارشی قالب** — مثلاً استفاده از فیلتری که وجود ندارد
   (``Invalid filter: 'as_widget'``) که کل یک صفحه را از کار می‌انداخت.

۲. **RecursionError در IncludeNode** — علتش این است که
   ``{# ... #}`` در جنگو فقط **یک‌خطی** است (الگوی ``tag_re`` در
   ``django/template/base.py`` فلگ ``re.DOTALL`` ندارد). اگر کامنت
   چندخطی با ``{# #}`` نوشته شود، متنش رندر می‌شود و ``{% include %}``
   داخلش واقعاً اجرا می‌شود؛ نتیجه یک include بازگشتی بی‌پایان است.

۳. **نشت متن کامنت به HTML** — همان ریشهٔ بالا، که باعث می‌شود متن
   توضیحات به‌عنوان محتوای قابل‌مشاهده به کاربر نمایش داده شود.

اجرا::

    python manage.py test core.tests.test_template_render_smoke
"""

import os
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.template import TemplateSyntaxError
from django.template.loader import get_template
from django.template.loader_tags import IncludeNode
from django.test import TestCase

User = get_user_model()

TEMPLATES_DIR = Path(settings.BASE_DIR) / "templates"

# صفحات کلیدی که باید برای یک کاربر مدیر کامل رندر شوند.
SUPERUSER_PAGES = [
    "/dashboard/",
    "/financial/",
    "/financial/reports/",
    "/financial/transactions/",
    "/financial/payments/entry/",
    "/financial/reconciliation/",
    "/customers/",
    "/products/",
    "/reservations/",
    "/leaves/management/",
    "/accounts/profile/",
    "/accounts/settings/",
    "/accounts/change-password/",
]

# صفحاتی که فقط برای نقش فروشنده در دسترس هستند.
SELLER_PAGES = [
    "/leaves/submit/",
    "/leaves/my/",
]

# نشانه‌های نشت متن کامنت یا پیام خطای جنگو به خروجی HTML.
LEAK_MARKERS = [
    "{% include",
    "{% comment",
    "{% endcomment",
    "{% load",
    "{% with",
    "{% if ",
    "{% endif",
    "TemplateSyntaxError",
    "Invalid filter",
    "maximum recursion depth exceeded",
    "Could not parse the remainder",
]

# الگوی کامنت چندخطی ``{# ... #}`` که در جنگو کامنت محسوب نمی‌شود.
MULTILINE_HASH_COMMENT_RE = re.compile(r"\{#[^#\n]*\n[^#]*?#\}", re.DOTALL)

# کامنت‌های واقعی جنگو (این‌ها قبل از هر اسکنی حذف می‌شوند، چون ممکن است
# نمونه‌کد ``{% include %}`` داشته باشند که نباید اجرا/گزارش شود).
COMMENT_BLOCK_RE = re.compile(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", re.DOTALL)
HASH_COMMENT_RE = re.compile(r"\{#.*?#\}", re.DOTALL)


def strip_template_comments(text: str) -> str:
    """حذف کامنت‌های واقعی قالب تا اسکن‌های ساختاری دقیق باشند."""
    return HASH_COMMENT_RE.sub("", COMMENT_BLOCK_RE.sub("", text))


class TemplateCompileTests(TestCase):
    """هر قالب پروژه باید بدون خطا کامپایل شود."""

    def test_all_templates_compile(self):
        broken = []
        for path in sorted(TEMPLATES_DIR.rglob("*.html")):
            name = path.relative_to(TEMPLATES_DIR).as_posix()
            try:
                get_template(name)
            except TemplateSyntaxError as exc:
                broken.append(f"{name}: {exc}")
            except Exception as exc:  # noqa: BLE001
                broken.append(f"{name}: {type(exc).__name__}: {exc}")
        self.assertEqual(broken, [], "قالب‌های ناسالم:\n" + "\n".join(broken))

    def test_no_multiline_hash_comments(self):
        """``{# ... #}`` چندخطی کامنت نیست و باید به ``{% comment %}`` تبدیل شود."""
        offenders = []
        for path in sorted(TEMPLATES_DIR.rglob("*.html")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if MULTILINE_HASH_COMMENT_RE.search(text):
                offenders.append(str(path.relative_to(TEMPLATES_DIR)))
        self.assertEqual(
            offenders, [],
            "این قالب‌ها کامنت چندخطی با {# #} دارند (کامنت نیستند و رندر می‌شوند):\n"
            + "\n".join(offenders),
        )

    def test_no_self_including_partials(self):
        """هیچ partial نباید خودش را include کند (ریشهٔ RecursionError)."""
        offenders = []
        for path in sorted(TEMPLATES_DIR.rglob("*.html")):
            name = path.relative_to(TEMPLATES_DIR).as_posix()
            text = strip_template_comments(
                path.read_text(encoding="utf-8", errors="ignore")
            )
            if re.search(r"\{%\s*include\s+['\"]" + re.escape(name) + r"['\"]", text):
                offenders.append(name)
        self.assertEqual(offenders, [], "include بازگشتی:\n" + "\n".join(offenders))


class TemplateRenderSmokeTests(TestCase):
    """صفحات کلیدی باید ۲۰۰ برگردانند و هیچ متن کامنتی نشت ندهند."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username="smoke-admin", email="a@example.com", password="x"
        )
        cls.seller = User.objects.create_user(
            username="smoke-seller", password="x", role=User.Role.SELLER
        )

    def _assert_pages_clean(self, user, paths):
        self.client.force_login(user)
        problems = []
        for path in paths:
            response = self.client.get(path, follow=True)
            if response.status_code != 200:
                problems.append(f"{path} -> HTTP {response.status_code}")
                continue
            body = response.content.decode("utf-8", errors="replace")
            leaks = [m for m in LEAK_MARKERS if m in body]
            if leaks:
                problems.append(f"{path} -> نشت: {leaks}")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_superuser_pages_render_clean(self):
        self._assert_pages_clean(self.admin, SUPERUSER_PAGES)

    def test_seller_pages_render_clean(self):
        self._assert_pages_clean(self.seller, SELLER_PAGES)


class PartialIncludeDepthTests(TestCase):
    """عمق include هر partial محدود است (محافظ در برابر بازگشت بی‌پایان)."""

    MAX_DEPTH = 6

    def _depth(self, template, seen, depth=0):
        if depth > self.MAX_DEPTH:
            raise AssertionError(f"عمق include بیش از حد: {seen}")
        from django.template.loader import get_template

        source = strip_template_comments(get_template(template).template.source)
        includes = re.findall(r"\{%\s*include\s+['\"]([^'\"]+)['\"]", source)
        best = depth
        for child in includes:
            if child in seen:
                raise AssertionError(f"چرخهٔ include: {' -> '.join(seen + [child])}")
            try:
                best = max(best, self._depth(child, seen + [child], depth + 1))
            except Exception:  # noqa: BLE001
                # قالب‌های داینامیک/ناموجود در این تست نادیده گرفته می‌شوند
                continue
        return best

    def test_partials_have_bounded_include_depth(self):
        for path in sorted((TEMPLATES_DIR / "partials").glob("*.html")):
            name = path.relative_to(TEMPLATES_DIR).as_posix()
            self._depth(name, [name])
