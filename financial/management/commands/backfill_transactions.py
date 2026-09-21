"""
دستور قدیمی «backfill_transactions» — اکنون صرفاً یک پوستهٔ سازگاری (shim).

دلیل تغییر (رفع ایراد بحرانی C-1):
    نسخهٔ قبلی این دستور فقط وجود تراکنش‌هایی با
    ``external_reference='legacy-backfill'`` را بررسی می‌کرد و هیچ توجهی به
    پرداخت‌های واقعیِ ثبت‌شده در سیستم مرحله‌ای نداشت. بنابراین اگر رزروی
    از قبل «بیعانه اول» واقعی داشت (و ``deposit_amount`` هم به‌عنوان کش همان
    مقدار بود)، این دستور یک تراکنش بیعانهٔ دوم با همان مبلغ می‌ساخت و پول
    دو بار شمرده می‌شد (نمونهٔ اثبات‌شده: ۲۷۰٬۰۰۰ → ۵۴۰٬۰۰۰).

راه‌حل:
    منطق انتقال داده به یک منبع واحد و idempotent منتقل شده است:
    ``ReservationPaymentService.materialize_legacy_payments`` که فقط مبالغ
    «باقی‌ماندهٔ منتقل‌نشده» را می‌سازد (``pending_legacy_amounts``) و اگر
    پرداخت واقعی وجود داشته باشد هیچ رکورد تکراری نمی‌سازد.

این دستور برای حفظ سازگاری با اسکریپت‌ها/کرون‌های قدیمی نگه داشته شده و
صرفاً اجرای امن را فراخوانی می‌کند.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'منسوخ: از «backfill_staged_payments» استفاده کنید. '
        'این دستور فقط برای سازگاری نگه داشته شده و اجرای امن را فراخوانی می‌کند.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='فقط گزارش بده و چیزی ذخیره نکن.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='حداکثر تعداد رزرو برای پردازش.',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            'دستور backfill_transactions منسوخ شده است و به '
            'backfill_staged_payments هدایت می‌شود (منبع واحد و idempotent).'
        ))

        forwarded = {}
        if options.get('dry_run'):
            forwarded['dry_run'] = True
        if options.get('limit'):
            forwarded['limit'] = options['limit']

        call_command('backfill_staged_payments', **forwarded)
