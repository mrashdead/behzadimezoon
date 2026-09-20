"""
انتقال داده‌های قدیمی بیعانه به پرداخت‌های مرحله‌ای.

این دستور idempotent است: اجرای چندباره رکورد تکراری نمی‌سازد و هیچ
داده‌ای را حذف نمی‌کند. رزروهای قدیمی که فقط ``deposit_amount`` یا
``remaining_payment_amount`` دارند، به تراکنش واقعی تبدیل می‌شوند تا
«بیعانه اول» و «پرداخت نهایی» در دفتر مالی و فاکتور دیده شوند.

نمونه اجرا:
    python manage.py backfill_staged_payments --dry-run
    python manage.py backfill_staged_payments
    python manage.py backfill_staged_payments --reservation 123
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from reservations.models import Reservation
from reservations.services.payment_stage_service import ReservationPaymentService


class Command(BaseCommand):
    help = 'انتقال بیعانه‌های قدیمی (فیلدهای کش‌شده) به پرداخت‌های مرحله‌ای و مرتب‌سازی شماره مراحل.'

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
        parser.add_argument(
            '--reservation',
            type=int,
            help='فقط یک رزرو مشخص را پردازش کن.',
        )
        parser.add_argument(
            '--skip-sequence',
            action='store_true',
            help='شماره مراحل تراکنش‌های موجود را بازسازی نکن.',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run')
        limit = options.get('limit')
        reservation_id = options.get('reservation')
        skip_sequence = options.get('skip_sequence')

        qs = Reservation.all_objects.all().order_by('pk')
        if reservation_id:
            qs = qs.filter(pk=reservation_id)
        if limit:
            qs = qs[:limit]

        migrated = 0
        already_ok = 0
        skipped = 0
        errors = []

        for reservation in qs.iterator():
            pending = ReservationPaymentService.pending_legacy_amounts(reservation)
            legacy_total = pending['deposit'] + pending['balance']

            if legacy_total <= 0:
                already_ok += 1
                continue

            creator = reservation.updated_by or reservation.created_by
            if creator is None:
                self.stdout.write(self.style.WARNING(
                    f'رزرو {reservation.pk}: کاربر ثبت‌کننده مشخص نیست؛ رد شد.'
                ))
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f'[dry-run] رزرو {reservation.pk}: '
                    f'بیعانه={pending["deposit"]:,} / مانده پرداخت={pending["balance"]:,}'
                )
                migrated += 1
                continue

            try:
                with transaction.atomic():
                    mapping = ReservationPaymentService.materialize_legacy_payments(
                        reservation, creator
                    )
                if mapping:
                    migrated += 1
                    self.stdout.write(
                        f'رزرو {reservation.pk}: {len(mapping)} پرداخت مرحله‌ای ساخته شد.'
                    )
                else:
                    already_ok += 1
            except Exception as exc:  # noqa: BLE001 - گزارش دقیق برای اپراتور
                errors.append((reservation.pk, str(exc)))
                self.stderr.write(
                    self.style.ERROR(f'رزرو {reservation.pk}: خطا -> {exc}')
                )

        sequence_updated = 0
        if not skip_sequence and not dry_run:
            sequence_updated = ReservationPaymentService.backfill_sequence_numbers()

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'پایان. منتقل‌شده: {migrated} | از قبل درست: {already_ok} | '
            f'رد شده: {skipped} | خطا: {len(errors)} | شماره‌گذاری‌شده: {sequence_updated}'
        ))
        if errors:
            self.stdout.write(self.style.WARNING(
                'رزروهای دارای خطا: ' + ', '.join(str(pk) for pk, _ in errors)
            ))
