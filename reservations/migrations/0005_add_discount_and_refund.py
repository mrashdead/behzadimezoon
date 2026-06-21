# Generated manual migration to add discount_type, discount_value and refunded_amount
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0004_reservation_remaining_paid_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservation',
            name='discount_type',
            field=models.CharField(default='NONE', max_length=10, verbose_name='نوع تخفیف'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='reservation',
            name='discount_value',
            field=models.PositiveIntegerField(default=0, verbose_name='مقدار تخفیف'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='reservation',
            name='refunded_amount',
            field=models.PositiveIntegerField(default=0, verbose_name='مبلغ مرجوعی'),
            preserve_default=False,
        ),
    ]
