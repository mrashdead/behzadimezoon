# Generated migration for adding payment_status, is_deleted and ReservationStatusLog
from django.conf import settings
from django.db import migrations, models
import django_jalali.db.models


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='reservation',
            name='payment_status',
            field=models.CharField(choices=[('UNPAID', 'پرداخت نشده'), ('PARTIAL', 'پرداخت جزئی'), ('PAID', 'پرداخت شده'), ('REFUNDED', 'پرداخت برگشتی')], default='UNPAID', max_length=20, verbose_name='وضعیت پرداخت'),
        ),
        migrations.AddField(
            model_name='reservation',
            name='is_deleted',
            field=models.BooleanField(default=False, db_index=True, verbose_name='حذف نرم'),
        ),
        migrations.CreateModel(
            name='ReservationStatusLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('old_status', models.CharField(max_length=20)),
                ('new_status', models.CharField(max_length=20)),
                ('changed_at', django_jalali.db.models.jDateTimeField(auto_now_add=True)),
                ('note', models.TextField(blank=True)),
                ('changed_by', models.ForeignKey(blank=True, null=True, on_delete=models.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('reservation', models.ForeignKey(on_delete=models.CASCADE, related_name='status_logs', to='reservations.reservation')),
            ],
            options={
                'ordering': ['-changed_at'],
            },
        ),
        migrations.AddIndex(
            model_name='reservation',
            index=models.Index(fields=['status'], name='reservations_status_idx'),
        ),
        migrations.AddIndex(
            model_name='reservation',
            index=models.Index(fields=['payment_status'], name='reservations_payment_status_idx'),
        ),
        migrations.AddIndex(
            model_name='reservation',
            index=models.Index(fields=['start_date'], name='reservations_start_date_idx'),
        ),
        migrations.AddIndex(
            model_name='reservation',
            index=models.Index(fields=['event_date'], name='reservations_event_date_idx'),
        ),
        migrations.AddIndex(
            model_name='reservation',
            index=models.Index(fields=['created_at'], name='reservations_created_at_idx'),
        ),
    ]
