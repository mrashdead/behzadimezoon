# Generated migration - Enhance Transaction, Guarantee, DamageRecord, CancellationRecord

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('financial', '0005_add_guarantee_damage_cancellation'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('products', '0001_initial'),
    ]

    operations = [
        # --- TRANSACTION ENHANCEMENTS ---
        migrations.AddField(
            model_name='transaction',
            name='customer',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='customer_transactions',
                to='customers.customer',
                verbose_name='مشتری'
            ),
        ),
        migrations.AddField(
            model_name='transaction',
            name='posting_status',
            field=models.CharField(
                max_length=20,
                choices=[('DRAFT', 'پیش‌نویس'), ('POSTED', 'ثبت شده')],
                default='POSTED',
                verbose_name='وضعیت ثبت',
                help_text='Controls whether transaction affects balances: DRAFT=tentative, POSTED=final'
            ),
        ),
        migrations.AddField(
            model_name='transaction',
            name='sequence_number',
            field=models.PositiveIntegerField(
                null=True,
                blank=True,
                db_index=True,
                verbose_name='شماره ترتیب',
                help_text='Sequential number for journal ordering; auto-assigned on posting'
            ),
        ),
        migrations.AddField(
            model_name='transaction',
            name='is_immutable',
            field=models.BooleanField(
                default=False,
                verbose_name='ناپذیر تغییر',
                help_text='If True, this transaction cannot be edited; only reversals allowed'
            ),
        ),
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(fields=['customer'], name='financial_t_custome_bd1e01_idx'),
        ),
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(fields=['posting_status'], name='financial_t_posting_b85e75_idx'),
        ),

        # --- GUARANTEE ENHANCEMENTS ---
        migrations.AddField(
            model_name='guarantee',
            name='dress',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='guarantees',
                to='products.dress',
                verbose_name='لباس'
            ),
        ),
        migrations.AddField(
            model_name='guarantee',
            name='refunded_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                verbose_name='تاریخ بازپرداخت وجه',
                help_text='When guarantee value was refunded (if applicable)'
            ),
        ),
        migrations.AddIndex(
            model_name='guarantee',
            index=models.Index(fields=['status'], name='financial_g_status_bb71aa_idx'),
        ),
        migrations.AddIndex(
            model_name='guarantee',
            index=models.Index(fields=['received_at'], name='financial_g_receive_226893_idx'),
        ),

        # --- DAMAGE RECORD ENHANCEMENTS ---
        migrations.AddField(
            model_name='damagerecord',
            name='dress',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='damage_records',
                to='products.dress',
                verbose_name='لباس'
            ),
        ),
        migrations.AddField(
            model_name='damagerecord',
            name='severity',
            field=models.CharField(
                max_length=20,
                choices=[('MINOR', 'جزئی'), ('MODERATE', 'متوسط'), ('SEVERE', 'شدید')],
                null=True,
                blank=True,
                verbose_name='شدت خسارت'
            ),
        ),
        migrations.AddField(
            model_name='damagerecord',
            name='detected_by',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='detected_damages',
                to=settings.AUTH_USER_MODEL,
                verbose_name='شناسایی شده توسط'
            ),
        ),
        migrations.AddField(
            model_name='damagerecord',
            name='approved_by',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='approved_damages',
                to=settings.AUTH_USER_MODEL,
                verbose_name='تایید شده توسط'
            ),
        ),
        migrations.AddField(
            model_name='damagerecord',
            name='dispute_status',
            field=models.CharField(
                max_length=20,
                choices=[('NONE', 'بدون نزاع'), ('OPEN', 'نزاع باز'), ('RESOLVED', 'حل شده')],
                default='NONE',
                verbose_name='وضعیت نزاع'
            ),
        ),
        migrations.AddField(
            model_name='damagerecord',
            name='dispute_opened_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                verbose_name='تاریخ باز کردن نزاع'
            ),
        ),
        migrations.AddField(
            model_name='damagerecord',
            name='dispute_resolved_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                verbose_name='تاریخ حل نزاع'
            ),
        ),
        migrations.AddField(
            model_name='damagerecord',
            name='dispute_notes',
            field=models.TextField(
                blank=True,
                verbose_name='یادداشت نزاع'
            ),
        ),
        migrations.AddIndex(
            model_name='damagerecord',
            index=models.Index(fields=['collected'], name='financial_d_collect_0f9c9a_idx'),
        ),
        migrations.AddIndex(
            model_name='damagerecord',
            index=models.Index(fields=['dispute_status'], name='financial_d_dispute_5846b0_idx'),
        ),

        # --- CANCELLATION RECORD ENHANCEMENTS ---
        migrations.AddField(
            model_name='cancellationrecord',
            name='cancelled_by',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='cancelled_reservations',
                to=settings.AUTH_USER_MODEL,
                verbose_name='لغو شده توسط'
            ),
        ),
        migrations.AddField(
            model_name='cancellationrecord',
            name='approved_by',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='approved_cancellations',
                to=settings.AUTH_USER_MODEL,
                verbose_name='تایید شده توسط'
            ),
        ),
        migrations.AddField(
            model_name='cancellationrecord',
            name='refund_method',
            field=models.CharField(
                max_length=20,
                choices=[('CARD', 'کارت به کارت'), ('CASH', 'نقدی'), ('TRANSFER', 'انتقال بانکی'), ('POS', 'کارتخوان')],
                null=True,
                blank=True,
                verbose_name='روش بازپرداخت'
            ),
        ),
        migrations.AddField(
            model_name='cancellationrecord',
            name='refund_posted_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                verbose_name='تاریخ ثبت بازپرداخت'
            ),
        ),
        migrations.AddField(
            model_name='cancellationrecord',
            name='refund_status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('REQUESTED', 'درخواست شده'),
                    ('APPROVED', 'تایید شده'),
                    ('POSTED', 'ثبت شده'),
                    ('COMPLETED', 'تکمیل شده'),
                ],
                default='REQUESTED',
                verbose_name='وضعیت بازپرداخت'
            ),
        ),
        migrations.AddField(
            model_name='cancellationrecord',
            name='approval_date',
            field=models.DateTimeField(
                null=True,
                blank=True,
                verbose_name='تاریخ تایید'
            ),
        ),
        migrations.AddField(
            model_name='cancellationrecord',
            name='approval_notes',
            field=models.TextField(
                blank=True,
                verbose_name='یادداشت تایید'
            ),
        ),
        migrations.AddIndex(
            model_name='cancellationrecord',
            index=models.Index(fields=['refund_status'], name='financial_c_refund__9d93af_idx'),
        ),
    ]
