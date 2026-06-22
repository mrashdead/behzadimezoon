# Generated migration for financial.Transaction
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('reservations', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.BigIntegerField()),
                ('type', models.CharField(choices=[('PAYMENT', 'پرداخت'), ('REFUND', 'مرجوع'), ('DISCOUNT', 'تخفیف'), ('DAMAGE', 'خسارت'), ('ADJUSTMENT', 'تعدیل دستی')], max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('note', models.TextField(blank=True)),
                ('reference', models.CharField(max_length=200, null=True, blank=True)),
                ('created_by', models.ForeignKey(on_delete=models.PROTECT, related_name='transactions', to=settings.AUTH_USER_MODEL)),
                ('reservation', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='transactions', to='reservations.reservation')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(fields=['type'], name='financial_transaction_type_idx'),
        ),
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(fields=['created_at'], name='financial_transaction_created_at_idx'),
        ),
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(fields=['reservation'], name='financial_transaction_reservation_idx'),
        ),
    ]
