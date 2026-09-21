"""
دستور قدیمی «backfill_financials» — اکنون صرفاً یک پوستهٔ سازگاری (shim).

دلیل تغییر (رفع ایراد H-3):
    این دستور یک پیاده‌سازی موازی و مستقل از انتقال دادهٔ مالی بود که با
    سیستم بیعانهٔ مرحله‌ای هم‌راستا نبود و در ساخت تراکنش از
    ``posting_status`` (که فقط یک property است، نه فیلد) استفاده می‌کرد.
    وجود دو پیاده‌سازی موازی، ریسک واگرایی محاسبات و دوباره‌شماری را
    ایجاد می‌کرد.

راه‌حل:
    منطق انتقال داده به منبع واحد و idempotent منتقل شده است:
    ``ReservationPaymentService.materialize_legacy_payments`` که فقط
    «مبالغ منتقل‌نشده» (``pending_legacy_amounts``) را می‌سازد و در صورت
    وجود پرداخت واقعی، رکورد تکراری نمی‌سازد.

این دستور برای حفظ سازگاری با اسکریپت‌ها/مستندات قدیمی نگه داشته شده و
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
            default=0,
            help='حداکثر تعداد رزرو برای پردازش (۰ = همه).',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            'دستور backfill_financials منسوخ شده است و به '
            'backfill_staged_payments هدایت می‌شود (منبع واحد و idempotent).'
        ))

        forwarded = {}
        if options.get('dry_run'):
            forwarded['dry_run'] = True
        if options.get('limit'):
            forwarded['limit'] = options['limit']

        call_command('backfill_staged_payments', **forwarded)
