"""اعتبارسنجی کلاس‌های کمکی تم (Bootstrap + custom.css) در قالب‌ها.

انگیزه
------
کلاس‌های کمکی مثل ``minw-90px`` اگر در CSS تعریف نشده باشند **هیچ خطایی
نمی‌دهند**؛ فقط بی‌اثر می‌مانند و ظاهر به‌هم می‌ریزد. تم این پروژه فقط
مضرب‌های ۲۵ پیکسل را دارد (``minw-50px``، ``minw-75px``، ``minw-100px`` …)
بنابراین ``minw-90px`` یا ``minw-220px`` بی‌اثر هستند.

این دستور خانواده‌های کلاسی «حساس» را در قالب‌ها پیدا می‌کند و با فهرست
کلاس‌های واقعاً تعریف‌شده در CSS مقایسه می‌کند.

نمونهٔ استفاده::

    python manage.py check_theme_classes
    python manage.py check_theme_classes --fail-on-missing   # برای CI
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

# خانواده‌هایی که فقط با پیشوند مشخص و الگوی دقیق بررسی می‌شوند.
# ساختار: prefix -> regex کامل نام کلاس (بدون نقطه)
FAMILIES = {
    "minw-": re.compile(r"minw-\d+px"),
    "avatar-": re.compile(r"avatar-(?:xxs|xs|sm|lg|xl|xxl)"),
    "text-size": re.compile(r"text-(?:1xs|2xs|3xs)"),
    "badge": re.compile(r"badge-sm"),
    "btn-action": re.compile(r"btn-action-(?:primary|secondary|success|danger|warning|info|light|dark)"),
    "theme-component": re.compile(
        r"(?:kpi-card|detail-card|section-card|page-head-card|empty-state|chart-box|app-toast)"
        r"(?:__[a-z-]+)?(?:--[a-z-]+)?"
    ),
    "theme-utility": re.compile(
        r"(?:card-gradient|table-row-rounded|stretched-link|border-dashed|bg-body-tertiary-subtle|min-w-0)"
    ),
}

CLASS_ATTR_RE = re.compile(r'class="([^"]*)"')
CSS_CLASS_DEF_RE = re.compile(r"\.([a-zA-Z][\w-]*)")

CSS_FILES = [
    # بوت‌استرپ در این پروژه داخل styles.css باندل شده است.
    "assets/css/styles.css",
    "assets/css/custom.css",
    "assets/css/reservations.css",
    "assets/css/reservation-combobox.css",
]

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "env", ".venv", "venv",
    "staticfiles", "media", "dist", "build", "flaticon",
}


class Command(BaseCommand):
    help = "اعتبارسنجی کلاس‌های کمکی تم در قالب‌ها (کشف کلاس‌های بی‌اثر)"

    def add_arguments(self, parser):
        parser.add_argument("--fail-on-missing", action="store_true")
        parser.add_argument(
            "--only",
            default=None,
            help="فقط یک خانواده را بررسی کن (مثلاً minw-)",
        )

    def _defined_classes(self) -> set[str]:
        base = Path(settings.BASE_DIR) / "static"
        defined: set[str] = set()
        for rel in CSS_FILES:
            path = base / rel
            if not path.exists():
                self.stderr.write(f"هشدار: فایل CSS پیدا نشد: {rel}")
                continue
            defined.update(CSS_CLASS_DEF_RE.findall(
                path.read_text(encoding="utf-8", errors="ignore")
            ))
        return defined

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR)
        templates_dir = base_dir / "templates"
        defined = self._defined_classes()

        families = FAMILIES
        if options.get("only"):
            key = options["only"]
            if key not in FAMILIES:
                self.stderr.write(self.style.ERROR(
                    f"خانوادهٔ ناشناخته: {key}\nموجود: {', '.join(FAMILIES)}"
                ))
                return
            families = {key: FAMILIES[key]}

        found: dict[str, dict[str, set[str]]] = {}

        for path in sorted(templates_dir.rglob("*.html")):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            rel = str(path.relative_to(base_dir))
            for attr in CLASS_ATTR_RE.findall(text):
                for token in attr.split():
                    for family, pattern in families.items():
                        if pattern.fullmatch(token) and token not in defined:
                            found.setdefault(token, {}).setdefault(family, set()).add(rel)

        if not found:
            self.stdout.write(self.style.SUCCESS(
                "تمام کلاس‌های کمکی تم به‌کاررفته معتبر هستند. ✔"
            ))
            return

        self.stdout.write(self.style.ERROR(
            f"\n{len(found)} کلاس بی‌اثر (در CSS تعریف نشده) پیدا شد:"
        ))
        for token in sorted(found):
            family = next(iter(found[token]))
            files = sorted(found[token][family])
            self.stdout.write(f"  ✗ {token}   [{family}]")
            for f in files[:5]:
                self.stdout.write(f"      {f}")
            if len(files) > 5:
                self.stdout.write(f"      … و {len(files) - 5} فایل دیگر")

        # پیشنهاد جایگزین نزدیک در همان خانواده
        self.stdout.write("\nنزدیک‌ترین کلاس‌های معتبر در همان خانواده:")
        for token in sorted(found):
            family = next(iter(found[token]))
            prefix = token.split("-")[0] + "-"
            candidates = sorted(
                c for c in defined
                if c.startswith(prefix) and FAMILIES[family].fullmatch(c)
            )
            if candidates:
                self.stdout.write(f"  {token}  →  {', '.join(candidates[:8])}")

        if options.get("fail_on_missing"):
            raise SystemExit(1)
