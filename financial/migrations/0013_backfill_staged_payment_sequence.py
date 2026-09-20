"""
مرتب‌سازی شماره مراحل پرداخت‌های مرحله‌ای (بیعانه‌ها).

پیش از افزودن «بیعانه مرحله‌ای»، فیلد ``sequence_number`` روی تراکنش‌ها
همیشه پر نمی‌شد. این مهاجرت به‌صورت idempotent آن را بر اساس ترتیب تاریخ
برای پرداخت‌های معتبر پر می‌کند تا برچسب‌های «بیعانه اول/دوم/...» پایدار
باشند. هیچ داده‌ای حذف یا تغییر مبلغ نمی‌شود.
"""

from django.db import migrations

STAGED_TYPES = ('DEPOSIT', 'PARTIAL_PAYMENT', 'FINAL_PAYMENT')


def backfill_sequence_numbers(apps, schema_editor):
    Transaction = apps.get_model('financial', 'Transaction')

    reservation_ids = (
        Transaction.objects.filter(transaction_type__in=STAGED_TYPES)
        .values_list('reservation_id', flat=True)
        .distinct()
    )

    for reservation_id in reservation_ids:
        if reservation_id is None:
            continue

        payments = list(
            Transaction.objects.filter(
                reservation_id=reservation_id,
                transaction_type__in=STAGED_TYPES,
                transaction_status='POSTED',
                is_voided=False,
            ).order_by('transaction_date', 'pk')
        )

        for position, tx in enumerate(payments, start=1):
            if tx.sequence_number != position:
                Transaction.objects.filter(pk=tx.pk).update(sequence_number=position)


def noop(apps, schema_editor):
    """بازگشت لازم نیست؛ شماره‌گذاری فقط داده مشتق‌شده است."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('financial', '0012_alter_cancellationrecord_refund_method'),
    ]

    operations = [
        migrations.RunPython(backfill_sequence_numbers, noop),
    ]
