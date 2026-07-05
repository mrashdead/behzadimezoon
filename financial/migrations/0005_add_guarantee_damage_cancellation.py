from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = False

    dependencies = [
        ('financial', '0004_add_reservation_snapshot_to_transaction'),
    ]

    operations = [
        migrations.CreateModel(
            name='Guarantee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tracking_code', models.CharField(max_length=200, verbose_name='کد مرجع')),
                ('guarantee_type', models.CharField(max_length=30, verbose_name='نوع تضمین')),
                ('description', models.TextField(blank=True, verbose_name='شرح')),
                ('estimated_value', models.BigIntegerField(null=True, blank=True, verbose_name='مبلغ تقریبی')),
                ('status', models.CharField(default='RECEIVED', max_length=20, verbose_name='وضعیت')),
                ('received_at', models.DateTimeField(auto_now_add=True, verbose_name='دریافت شده در')),
                ('returned_at', models.DateTimeField(null=True, blank=True, verbose_name='بازگردانده شده در')),
                ('notes', models.TextField(blank=True, verbose_name='یادداشت')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='guarantees', to='customers.customer')),
                ('reservation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='guarantees', to='reservations.reservation')),
            ],
            options={
                'verbose_name': 'تضمین',
                'verbose_name_plural': 'تضمین‌ها',
            },
        ),
        migrations.CreateModel(
            name='DamageRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('damage_type', models.CharField(max_length=100, verbose_name='نوع خسارت')),
                ('description', models.TextField(blank=True, verbose_name='شرح')),
                ('amount', models.BigIntegerField(null=True, blank=True, verbose_name='مبلغ خسارت')),
                ('detected_at', models.DateTimeField(auto_now_add=True, verbose_name='شناسایی در')),
                ('collected', models.BooleanField(default=False, verbose_name='پرداخت شده')),
                ('payment_reference', models.CharField(max_length=200, null=True, blank=True, verbose_name='کد پیگیری پرداخت')),
                ('notes', models.TextField(blank=True, verbose_name='یادداشت')),
                ('reservation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='damage_records', to='reservations.reservation')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='damage_records', to='customers.customer')),
                ('related_transaction', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True, related_name='+', to='financial.transaction')),
            ],
            options={
                'verbose_name': 'خسارت',
                'verbose_name_plural': 'خسارت‌ها',
            },
        ),
        migrations.CreateModel(
            name='CancellationRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField(blank=True, verbose_name='دلیل لغو')),
                ('cancelled_at', models.DateTimeField(auto_now_add=True, verbose_name='تاریخ لغو')),
                ('deposit_at_cancel', models.BigIntegerField(null=True, blank=True, verbose_name='بیعانه در زمان لغو')),
                ('refund_amount', models.BigIntegerField(null=True, blank=True, verbose_name='مبلغ بازپرداخت')),
                ('penalty_amount', models.BigIntegerField(null=True, blank=True, verbose_name='مبلغ جریمه نگه‌داشته‌شده')),
                ('notes', models.TextField(blank=True, verbose_name='یادداشت')),
                ('reservation', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='cancellation_record', to='reservations.reservation')),
            ],
            options={
                'verbose_name': 'رکورد لغو',
                'verbose_name_plural': 'رکوردهای لغو',
            },
        ),
    ]
