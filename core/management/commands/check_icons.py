"""بررسی اعتبار نام آیکون‌های فلیتیکون به‌کاررفته در قالب‌ها.

انگیزه
------
کتابخانهٔ Flaticon UIcons کلاس‌ها را به‌شکل ``.fi.fi-rr-<name>:before`` تعریف
می‌کند. اگر نام آیکون غلط باشد هیچ خطایی رخ نمی‌دهد؛ فقط یک مستطیل خالی
نمایش داده می‌شود. این دستور تمام قالب‌ها را اسکن می‌کند و نام‌های نامعتبر
را گزارش می‌دهد تا قبل از دیده‌شدن توسط کاربر پیدا شوند.

نکتهٔ مهم: فایل ``css/all/all.css`` فقط ``@import`` است و هیچ تعریفی ندارد؛
بنابراین برای استخراج نام‌های معتبر باید فایل‌های واقعی
``{regular,bold,solid,thin}/{rounded,straight}.css`` و ``brands/all.css``
با هم خوانده شوند.

نمونهٔ استفاده::

    python manage.py check_icons
    python manage.py check_icons --fail-on-missing   # برای CI
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

# فقط کلاس‌هایی که با یکی از این پیشوندها شروع می‌شوند «نام آیکون» هستند.
ICON_PREFIXES = ("fi-rr-", "fi-br-", "fi-sr-", "fi-tr-", "fi-bs-", "fi-ts-", "fi-")

# الگوی استخراج نام آیکون از متن قالب/فایل
ICON_RE = re.compile(r"\bfi-(?:rr|br|sr|tr|bs|ts)-[a-z0-9]+(?:-[a-z0-9]+)*")

# الگوی تعریف کلاس در CSS
CSS_DEF_RE = re.compile(r"\.(fi-(?:rr|br|sr|tr|bs|ts)-[a-z0-9-]+)\s*:\s*before")

# فایل‌های CSS که واقعاً تعریف آیکون‌ها را دارند.
CSS_RELATIVE_PATHS = [
    "assets/libs/flaticon/css/regular/rounded.css",
    "assets/libs/flaticon/css/regular/straight.css",
    "assets/libs/flaticon/css/bold/rounded.css",
    "assets/libs/flaticon/css/bold/straight.css",
    "assets/libs/flaticon/css/solid/rounded.css",
    "assets/libs/flaticon/css/solid/straight.css",
    "assets/libs/flaticon/css/thin/rounded.css",
    "assets/libs/flaticon/css/thin/straight.css",
    "assets/libs/flaticon/css/brands/all.css",
]

# پوشه‌هایی که اسکن نمی‌شوند
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "env", ".venv", "venv",
    "staticfiles", "media", "dist", "build", "flaticon",
}


class Command(BaseCommand):
    help = "اعتبارسنجی نام آیکون‌های فلیتیکون در تمام قالب‌ها و فایل‌های JS/CSS"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fail-on-missing",
            action="store_true",
            help="در صورت یافتن آیکون نامعتبر با کد خروج ۱ تمام شود (مناسب CI)",
        )
        parser.add_argument(
            "--scan",
            action="append",
            default=None,
            help="مسیر اضافی برای اسکن (قابل تکرار). پیش‌فرض: templates/ و static/",
        )

    # ------------------------------------------------------------------ helpers
    def _defined_icons(self) -> set[str]:
        base = Path(settings.BASE_DIR) / "static"
        defined: set[str] = set()
        for rel in CSS_RELATIVE_PATHS:
            path = base / rel
            if not path.exists():
                continue
            defined.update(CSS_DEF_RE.findall(path.read_text(encoding="utf-8", errors="ignore")))
        return defined

    def _iter_source_files(self, roots: list[Path]):
        extensions = {".html", ".htm", ".js", ".css", ".py"}
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in extensions:
                    continue
                if any(part in SKIP_DIRS for part in path.parts):
                    continue
                yield path

    def _clean(self, name: str) -> str | None:
        """رد کردن نام‌های ناقص/پویا که از عبارت‌های قالب می‌آیند."""
        if name.endswith("-") or "--" in name:
            return None
        return name

    def _extract(self, text: str):
        """استخراج نام آیکون‌ها با نادیده‌گرفتن نام‌های پویای قالب.

        مثلاً ``fi-rr-arrow-{% if x %}up{% else %}down{% endif %}`` یک نام
        پویا است و نباید به‌عنوان آیکون نامعتبر گزارش شود.
        """
        for match in ICON_RE.finditer(text):
            tail = text[match.end():match.end() + 3]
            # اگر بعد از نام یک «-» و سپس شروع تگ قالب بیاید، نام پویا است.
            if tail.startswith("-{") or tail.startswith("-{%"):
                continue
            name = self._clean(match.group(0))
            if name:
                yield name

    # ------------------------------------------------------------------- handle
    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR)
        roots = [base_dir / "templates", base_dir / "static"]
        for extra in options.get("scan") or []:
            roots.append(Path(extra))

        defined = self._defined_icons()
        if not defined:
            self.stderr.write(self.style.ERROR(
                "هیچ تعریف آیکونی در فایل‌های CSS فلیتیکون پیدا نشد. "
                "مسیر static/assets/libs/flaticon/css را بررسی کنید."
            ))
            return

        self.stdout.write(f"آیکون‌های معتبر در CSS: {len(defined)}")

        usages: dict[str, set[str]] = {}
        for path in self._iter_source_files(roots):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for name in self._extract(text):
                usages.setdefault(name, set()).add(str(path.relative_to(base_dir)))

        missing = {name: files for name, files in usages.items() if name not in defined}
        used = len(usages)

        if not missing:
            self.stdout.write(self.style.SUCCESS(
                f"تمام {used} آیکون به‌کاررفته معتبر هستند. ✔"
            ))
            return

        self.stdout.write(self.style.ERROR(
            f"\n{len(missing)} آیکون نامعتبر از {used} آیکون به‌کاررفته:"
        ))
        for name in sorted(missing):
            files = sorted(missing[name])
            self.stdout.write(f"  ✗ {name}")
            for f in files[:6]:
                self.stdout.write(f"      {f}")
            if len(files) > 6:
                self.stdout.write(f"      … و {len(files) - 6} فایل دیگر")

        # پیشنهاد نام‌های نزدیک
        self.stdout.write("\nپیشنهاد نزدیک‌ترین نام‌های معتبر:")
        for name in sorted(missing):
            core = name.replace("fi-rr-", "").replace("fi-br-", "")
            parts = [p for p in core.split("-") if len(p) > 2]
            candidates = [
                d for d in defined
                if parts and all(any(p in seg for seg in d.split("-")) for p in parts[:2])
            ][:4]
            if candidates:
                self.stdout.write(f"  {name}  →  {', '.join(sorted(candidates))}")

        if options.get("fail_on_missing"):
            raise SystemExit(1)
