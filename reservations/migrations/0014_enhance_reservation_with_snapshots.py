# Generated migration - Enhance Reservation with financial snapshots

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0013_add_reservation_archive_snapshot'),
    ]

    operations = [
        # Add snapshot fields to preserve historical financial truth
        migrations.AddField(
            model_name='reservation',
            name='dress_daily_price_snapshot',
            field=models.PositiveIntegerField(
                null=True,
                blank=True,
                verbose_name='قیمت روزانه لباس در زمان رزرو (snapshot)',
                help_text='Immutable snapshot of dress.daily_rent_price at time of reservation creation'
            ),
        ),
        migrations.AddField(
            model_name='reservation',
            name='customer_phone_snapshot',
            field=models.CharField(
                max_length=15,
                blank=True,
                verbose_name='شماره تماس عروس در زمان رزرو (snapshot)',
                help_text='Snapshot of customer phone for historical audit'
            ),
        ),
        migrations.AddField(
            model_name='reservation',
            name='financial_snapshot',
            field=models.JSONField(
                null=True,
                blank=True,
                verbose_name='snapshot مالی رزرو',
                help_text='JSON snapshot of financial state captured at key events (deposit, balance, return, etc.)'
            ),
        ),
        # Add business-level computed snapshot field
        migrations.AddField(
            model_name='reservation',
            name='total_cash_collected_snapshot',
            field=models.PositiveIntegerField(
                default=0,
                verbose_name='کل نقد دریافت شده (snapshot)',
                help_text='Snapshot of total cash collected: deposit + remaining_payment - refunds'
            ),
        ),
    ]
