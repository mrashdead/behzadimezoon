
# financial/models.py - Redesigned Models

from django.db import models
from django.conf import settings
from django.utils import timezone
from django_jalali.db import models as jmodels

User = settings.AUTH_USER_MODEL


class FinancialAccount(models.Model):
    """
    حساب‌های مالی برای دسته‌بندی بهتر
    """
    class AccountType(models.TextChoices):
        CASH = 'CASH', 'صندوق'
        BANK = 'BANK', 'حساب بانکی'
        EXPENSE = 'EXPENSE', 'حساب هزینه'
        RECEIVABLE = 'RECEIVABLE', 'حساب مطالبات'

    code = models.CharField(max_length=20, unique=True, verbose_name='کد حساب')
    name = models.CharField(max_length=200, verbose_name='نام حساب')
    account_type = models.CharField(max_length=20, choices=AccountType.choices, verbose_name='نوع حساب')
    balance = models.BigIntegerField(default=0, verbose_name='تراز فعلی')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    parent_account = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name='child_accounts', verbose_name='حساب والد')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')

    class Meta:
        verbose_name = 'حساب مالی'
        verbose_name_plural = 'حساب‌های مالی'
        ordering = ['code']
        indexes = [
            models.Index(fields=['account_type']),
            models.Index(fields=['code']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class TransactionCategory(models.Model):
    """
    دسته‌بندی تراکنش‌ها
    """
    class CategoryType(models.TextChoices):
        INCOME = 'INCOME', 'درآمد'
        EXPENSE = 'EXPENSE', 'هزینه'
        TRANSFER = 'TRANSFER', 'انتقال'
        ADJUSTMENT = 'ADJUSTMENT', 'تعدیل'

    name = models.CharField(max_length=100, verbose_name='نام دسته')
    category_type = models.CharField(max_length=20, choices=CategoryType.choices, verbose_name='نوع دسته')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    color = models.CharField(max_length=7, default='#6c757d', verbose_name='رنگ')
    icon = models.CharField(max_length=50, blank=True, verbose_name='آیکون')

    class Meta:
        verbose_name = 'دسته تراکنش'
        verbose_name_plural = 'دسته‌های تراکنش'
        ordering = ['name']

    def __str__(self):
        return self.name


class TransactionQuerySet(models.QuerySet):
    """Queryset helpers used by aggregation/reporting services."""

    def _rewrite_legacy_filter_kwargs(self, kwargs):
        new_kwargs = {}
        for k, v in kwargs.items():
            parts = k.split('__')
            if parts[0] == 'type':
                parts[0] = 'transaction_type'
                new_key = '__'.join(parts)
            else:
                new_key = k
            new_kwargs[new_key] = v
        return new_kwargs

    def filter(self, *args, **kwargs):
        kwargs = self._rewrite_legacy_filter_kwargs(kwargs)
        return super().filter(*args, **kwargs)

    def exclude(self, *args, **kwargs):
        kwargs = self._rewrite_legacy_filter_kwargs(kwargs)
        return super().exclude(*args, **kwargs)

    def cash_in(self):
        # Cash inflows: deposits, payments, damage payments (posted only)
        return self.filter(
            transaction_status=Transaction.TransactionStatus.POSTED,
            transaction_type__in=[
                Transaction.TransactionType.DEPOSIT,
                Transaction.TransactionType.FINAL_PAYMENT,
                Transaction.TransactionType.PARTIAL_PAYMENT,
                Transaction.TransactionType.DAMAGE_PAYMENT,
                Transaction.TransactionType.PENALTY_INCOME,
                Transaction.TransactionType.TRANSFER_IN,
                Transaction.TransactionType.ADJUSTMENT_IN,
            ],
        )

    def cash_out(self):
        return self.filter(
            transaction_status=Transaction.TransactionStatus.POSTED,
            transaction_type__in=[
                Transaction.TransactionType.REFUND,
                Transaction.TransactionType.TRANSFER_OUT,
            ],
        )

    def accrual(self):
        return self.filter(
            transaction_status=Transaction.TransactionStatus.POSTED,
            transaction_type__in=[
                Transaction.TransactionType.ADJUSTMENT,
                Transaction.TransactionType.ADJUSTMENT_IN,
                Transaction.TransactionType.ADJUSTMENT_OUT,
                Transaction.TransactionType.DISCOUNT,
                Transaction.TransactionType.DAMAGE_CHARGE,
                Transaction.TransactionType.CANCELLATION_FEE,
            ],
        )

    def receivable(self):
        return self.filter(
            transaction_status=Transaction.TransactionStatus.POSTED,
            transaction_type__in=[
                Transaction.TransactionType.CANCELLATION_FEE,
            ],
        )

    def for_reservation(self, reservation):
        return self.filter(reservation=reservation)


class TransactionManager(models.Manager.from_queryset(TransactionQuerySet)):
    pass


class Transaction(models.Model):
    """
    مدل پیشرفته تراکنش با قابلیت‌های بیشتر.
    برای حفظ سازگاری با کدهای قدیمی، نام‌های قدیمی فیلدها به‌صورت
    پراپرتی/آلیاس در دسترس باقی مانده‌اند.
    """
    class TransactionType(models.TextChoices):
        # Income types
        DEPOSIT = 'DEPOSIT', 'بیعانه'
        FINAL_PAYMENT = 'FINAL_PAYMENT', 'پرداخت نهایی'
        PARTIAL_PAYMENT = 'PARTIAL_PAYMENT', 'پرداخت جزئی'
        DAMAGE_PAYMENT = 'DAMAGE_PAYMENT', 'وصول خسارت'
        PENALTY_INCOME = 'PENALTY_INCOME', 'جریمه دریافتی'
        DAMAGE_CHARGE = 'DAMAGE_CHARGE', 'خسارت (تعهدی)'
        DISCOUNT = 'DISCOUNT', 'تخفیف'
        PAYMENT = 'PAYMENT', 'پرداخت عمومی'
        ADJUSTMENT = 'ADJUSTMENT', 'تعدیل دستی'

        # Expense types
        LAUNDRY_EXPENSE = 'LAUNDRY_EXPENSE', 'هزینه خشکشویی'
        REPAIR_EXPENSE = 'REPAIR_EXPENSE', 'هزینه تعمیر'
        SUPPLY_EXPENSE = 'SUPPLY_EXPENSE', 'هزینه لوازم'
        UTILITY_EXPENSE = 'UTILITY_EXPENSE', 'هزینه‌های جانبی'
        STAFF_SALARY = 'STAFF_SALARY', 'حقوق کارمندان'
        RENT_EXPENSE = 'RENT_EXPENSE', 'هزینه اجاره'
        MARKETING_EXPENSE = 'MARKETING_EXPENSE', 'هزینه تبلیغات'

        # Transaction types
        REFUND = 'REFUND', 'بازپرداخت'
        CANCELLATION_FEE = 'CANCELLATION_FEE', 'جریمه لغو'
        TRANSFER_IN = 'TRANSFER_IN', 'انتقال ورودی'
        TRANSFER_OUT = 'TRANSFER_OUT', 'انتقال خروجی'
        ADJUSTMENT_IN = 'ADJUSTMENT_IN', 'تعدیل ورودی'
        ADJUSTMENT_OUT = 'ADJUSTMENT_OUT', 'تعدیل خروجی'

    # Legacy alias so old code (Transaction.Type.DEPOSIT) keeps working.
    Type = TransactionType

    class TransactionStatus(models.TextChoices):
        DRAFT = 'DRAFT', 'پیش‌نویس'
        PENDING = 'PENDING', 'در انتظار تأیید'
        APPROVED = 'APPROVED', 'تأیید شده'
        POSTED = 'POSTED', 'ثبت شده'
        VOIDED = 'VOIDED', 'ابطال شده'
        REVERSED = 'REVERSED', 'برگردانده شده'

    # Legacy aliases
    PostingStatus = TransactionStatus

    class Category(models.TextChoices):
        """Legacy category namespace (CASH / ACCRUAL) preserved for old code."""
        CASH = 'CASH', 'نقدی'
        ACCRUAL = 'ACCRUAL', 'تعهدی'

    # TYPE -> accrual/cash mapping (legacy compatibility for reporting)
    TYPE_CATEGORY_MAP = {
        TransactionType.DEPOSIT: 'CASH',
        TransactionType.FINAL_PAYMENT: 'CASH',
        TransactionType.PARTIAL_PAYMENT: 'CASH',
        TransactionType.PAYMENT: 'CASH',
        TransactionType.DAMAGE_PAYMENT: 'CASH',
        TransactionType.PENALTY_INCOME: 'CASH',
        TransactionType.REFUND: 'CASH',
        TransactionType.TRANSFER_IN: 'CASH',
        TransactionType.TRANSFER_OUT: 'CASH',
        TransactionType.ADJUSTMENT_IN: 'ACCRUAL',
        TransactionType.ADJUSTMENT_OUT: 'ACCRUAL',
        TransactionType.ADJUSTMENT: 'ACCRUAL',
        TransactionType.DISCOUNT: 'ACCRUAL',
        TransactionType.DAMAGE_CHARGE: 'ACCRUAL',
        TransactionType.CANCELLATION_FEE: 'ACCRUAL',
    }

    # Core fields
    transaction_number = models.CharField(
        max_length=30, unique=True, verbose_name='شماره تراکنش', editable=False, null=True, blank=True
    )
    transaction_type = models.CharField(
        max_length=30, choices=TransactionType.choices, verbose_name='نوع تراکنش',
        db_column='transaction_type', default=TransactionType.DEPOSIT
    )
    transaction_status = models.CharField(
        max_length=20, choices=TransactionStatus.choices,
        default=TransactionStatus.POSTED, verbose_name='وضعیت',
    )

    # Financial details
    amount = models.BigIntegerField(verbose_name='مبلغ')
    currency = models.CharField(max_length=3, default='IRR', verbose_name='واحد پول')

    # References
    reservation = models.ForeignKey(
        'reservations.Reservation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transactions', verbose_name='رزرو مرتبط',
    )
    customer = models.ForeignKey(
        'customers.Customer', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transactions', verbose_name='مشتری',
    )
    account = models.ForeignKey(
        FinancialAccount, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transactions', verbose_name='حساب',
    )
    category = models.ForeignKey(
        TransactionCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transactions', verbose_name='دسته',
    )

    # Payment details
    payment_method = models.CharField(
        max_length=20, choices=[('CASH', 'نقدی'), ('CARD', 'کارت به کارت'),
                                ('TRANSFER', 'انتقال بانکی'), ('POS', 'کارتخوان')],
        null=True, blank=True, verbose_name='روش پرداخت',
    )
    payment_reference = models.CharField(max_length=200, blank=True, verbose_name='کد رهگیری')
    receipt_number = models.CharField(max_length=100, blank=True, verbose_name='شماره رسید')

    # Dates
    transaction_date = models.DateTimeField(
        db_index=True, verbose_name='تاریخ تراکنش', default=timezone.now,
    )
    value_date = models.DateField(null=True, blank=True, verbose_name='تاریخ ارزش‌آفرینی')
    due_date = models.DateField(null=True, blank=True, verbose_name='تاریخ سررسید')

    # Related transactions
    related_transaction = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='related_transactions', verbose_name='تراکنش مرتبط',
    )

    # Metadata
    description = models.TextField(blank=True, default='', verbose_name='توضیحات')
    notes = models.TextField(blank=True, default='', verbose_name='یادداشت')
    attachment = models.FileField(
        upload_to='financial/attachments/%Y/%m/', null=True, blank=True, verbose_name='پیوست',
    )

    # Legacy snapshot / audit fields retained for backward compatibility
    external_reference = models.CharField(max_length=200, blank=True, default='', verbose_name='ارجاع خارجی')
    note = models.TextField(blank=True, default='', verbose_name='یادداشت (legacy)')
    reservation_snapshot = models.JSONField(null=True, blank=True, verbose_name='اسنپ‌شات رزرو')
    sequence_number = models.PositiveIntegerField(null=True, blank=True, db_index=True, verbose_name='شماره ترتیب')
    is_immutable = models.BooleanField(default=False, verbose_name='ناپذیر تغییر')

    # Audit
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='created_transactions',
        verbose_name='ایجادکننده', null=True, blank=True,
    )
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_transactions', verbose_name='تأییدکننده',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین بروزرسانی')
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ تأیید')
    posted_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ ثبت')
    voided_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ ابطال')
    voided_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='voided_transactions', verbose_name='ابطال‌کننده',
    )
    void_reason = models.TextField(blank=True, default='', verbose_name='دلیل ابطال')

    # System fields
    is_reconciled = models.BooleanField(default=False, verbose_name='هماهنگ شده')
    reconciled_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ هماهنگی')
    is_posted = models.BooleanField(default=False, verbose_name='ثبت شده')
    is_voided = models.BooleanField(default=False, editable=False, verbose_name='ابطال شده')

    objects = TransactionManager()

    class Meta:
        verbose_name = 'تراکنش'
        verbose_name_plural = 'تراکنش‌ها'
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['transaction_type']),
            models.Index(fields=['transaction_status']),
            models.Index(fields=['transaction_date']),
            models.Index(fields=['reservation']),
            models.Index(fields=['account']),
            models.Index(fields=['is_reconciled']),
            models.Index(fields=['customer']),
            models.Index(fields=['payment_method']),
        ]

    def __str__(self):
        marker = "[DRAFT] " if not self.is_posted_status else ""
        return f"{marker}{self.get_transaction_type_display()} {self.amount} تومان ({self.transaction_date:%Y-%m-%d %H:%M})"

    def save(self, *args, **kwargs):
        # Auto-generate transaction number
        if not self.transaction_number:
            prefix = (self.transaction_type.split('_')[0]
                      if self.transaction_type else 'TXN')
            date_str = timezone.now().strftime('%Y%m%d')
            last_txn = Transaction.objects.filter(
                transaction_number__startswith=f'{prefix}{date_str}'
            ).order_by('-transaction_number').first()
            if last_txn and last_txn.transaction_number:
                try:
                    last_seq = int(last_txn.transaction_number[-4:])
                    new_seq = last_seq + 1
                except ValueError:
                    new_seq = 1
            else:
                new_seq = 1
            self.transaction_number = f"{prefix}{date_str}{new_seq:04d}"

        # Keep is_posted in sync with transaction_status
        self.is_posted = (self.transaction_status == self.TransactionStatus.POSTED)

        # Sync legacy fields
        if self.note and not self.notes:
            self.notes = self.note
        if self.external_reference and not self.payment_reference:
            self.payment_reference = self.external_reference

        super().save(*args, **kwargs)

    # -----------------------
    # Legacy field aliases
    # -----------------------
    @property
    def type(self):
        """Legacy alias for transaction_type."""
        return self.transaction_type

    @type.setter
    def type(self, value):
        self.transaction_type = value

    @property
    def posting_status(self):
        """Legacy alias for transaction_status."""
        return self.transaction_status

    @posting_status.setter
    def posting_status(self, value):
        self.transaction_status = value

    @property
    def category_value(self):
        """Derived category (CASH/ACCRUAL) for legacy compatibility."""
        return self.TYPE_CATEGORY_MAP.get(self.transaction_type, 'CASH')

    # -----------------------
    # Status helpers
    # -----------------------
    @property
    def is_draft(self):
        return self.transaction_status == self.TransactionStatus.DRAFT

    @property
    def is_posted_status(self):
        return self.transaction_status == self.TransactionStatus.POSTED

    @property
    def can_be_voided(self):
        return not self.is_voided and self.transaction_status in [
            self.TransactionStatus.POSTED, self.TransactionStatus.APPROVED
        ]

    @property
    def is_income(self):
        return self.transaction_type in [
            self.TransactionType.DEPOSIT,
            self.TransactionType.FINAL_PAYMENT,
            self.TransactionType.PARTIAL_PAYMENT,
            self.TransactionType.PAYMENT,
            self.TransactionType.DAMAGE_PAYMENT,
            self.TransactionType.PENALTY_INCOME,
            self.TransactionType.TRANSFER_IN,
            self.TransactionType.ADJUSTMENT_IN,
        ]

    @property
    def is_inflow(self):
        return self.is_income

    @property
    def is_outflow(self):
        return self.transaction_type in [
            self.TransactionType.REFUND,
            self.TransactionType.TRANSFER_OUT,
        ]

    @property
    def is_expense(self):
        return self.transaction_type in [
            self.TransactionType.LAUNDRY_EXPENSE,
            self.TransactionType.REPAIR_EXPENSE,
            self.TransactionType.SUPPLY_EXPENSE,
            self.TransactionType.UTILITY_EXPENSE,
            self.TransactionType.STAFF_SALARY,
            self.TransactionType.RENT_EXPENSE,
            self.TransactionType.MARKETING_EXPENSE,
            self.TransactionType.TRANSFER_OUT,
            self.TransactionType.ADJUSTMENT_OUT,
        ]

    @property
    def is_cash(self):
        return self.category_value == 'CASH'

    @property
    def is_accrual(self):
        return self.category_value == 'ACCRUAL'

    @property
    def is_reversible(self):
        return not self.is_immutable

    @property
    def signed_amount(self):
        """مبلغ با علامت (+ برای درآمد، - برای هزینه/بازپرداخت/تخفیف)"""
        if self.transaction_type in (
            self.TransactionType.REFUND,
            self.TransactionType.DISCOUNT,
            self.TransactionType.TRANSFER_OUT,
            self.TransactionType.ADJUSTMENT_OUT,
        ):
            return -(self.amount or 0)
        return self.amount or 0

    @property
    def description_text(self):
        """Human-readable description (legacy compat)."""
        res_label = f"رزرو #{self.reservation_id}" if self.reservation_id else "تراکنش بدون رزرو مرتبط"
        try:
            base = f"{self.get_transaction_type_display()} {res_label}"
        except Exception:
            base = f"{self.transaction_type} {res_label}"
        suffix = f" — {self.notes}" if self.notes else ""
        return f"{base}{suffix}"


class PaymentAllocation(models.Model):
    """
    تخصیص پرداخت به آیتم‌های مختلف (برای پرداخت‌های ترکیبی)
    """
    payment_transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE,
                                        related_name='allocations')
    reservation = models.ForeignKey('reservations.Reservation', on_delete=models.SET_NULL,
                                null=True, blank=True)
    allocated_amount = models.BigIntegerField(verbose_name='مبلغ تخصیص یافته')
    allocated_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ تخصیص')

    class Meta:
        verbose_name = 'تخصیص پرداخت'
        verbose_name_plural = 'تخصیص‌های پرداخت'
        ordering = ['-allocated_at']


class ReconciliationEntry(models.Model):
    """
    ورودی هماهنگی مالی برای رفع اختلافات
    """
    class Status(models.TextChoices):
        OPEN = 'OPEN', 'باز'
        RESOLVED = 'RESOLVED', 'حل شده'
        IGNORED = 'IGNORED', 'نادیده گرفته شده'

    reconciliation_date = jmodels.jDateField(verbose_name='تاریخ هماهنگی')
    opening_balance = models.BigIntegerField(verbose_name='تراز افتتاحی')
    closing_balance = models.BigIntegerField(verbose_name='تراز اختتاح')
    difference = models.BigIntegerField(verbose_name='تفاوت')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    notes = models.TextField(blank=True, verbose_name='یادداشت')
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name='حل کننده')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ حل')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')

    class Meta:
        verbose_name = 'ورودی هماهنگی'
        verbose_name_plural = 'ورودی‌های هماهنگی'
        ordering = ['-reconciliation_date']
        indexes = [
            models.Index(fields=['reconciliation_date']),
            models.Index(fields=['status']),
        ]


# ---------------------------------------------------------------------------
# Legacy models (kept for backward compatibility with reservations/admin.py,
# financial/admin.py, and damage/cancellation services)
# ---------------------------------------------------------------------------

from reservations.constants import PaymentMethod as _LegacyPaymentMethod  # noqa: E402


class Guarantee(models.Model):
    RECEIVED = 'RECEIVED'
    RETURNED = 'RETURNED'
    FORFEITED = 'FORFEITED'
    STATUS_CHOICES = (
        (RECEIVED, 'دریافت‌شده'),
        (RETURNED, 'بازگردانده‌شده'),
        (FORFEITED, 'حفظ‌شده'),
    )

    reservation = models.ForeignKey(
        'reservations.Reservation', on_delete=models.CASCADE,
        related_name='guarantees', verbose_name='رزرو',
    )
    customer = models.ForeignKey(
        'customers.Customer', on_delete=models.CASCADE,
        related_name='guarantees', verbose_name='مشتری',
    )
    dress = models.ForeignKey(
        'products.Dress', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='guarantees', verbose_name='لباس',
    )
    tracking_code = models.CharField(max_length=200, verbose_name='کد مرجع')
    guarantee_type = models.CharField(max_length=30, verbose_name='نوع تضمین')
    description = models.TextField(blank=True, default='', verbose_name='شرح')
    estimated_value = models.BigIntegerField(null=True, blank=True, verbose_name='مبلغ تقریبی')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=RECEIVED, verbose_name='وضعیت',
    )
    received_at = models.DateTimeField(auto_now_add=True, verbose_name='دریافت شده در')
    returned_at = models.DateTimeField(null=True, blank=True, verbose_name='بازگردانده شده در')
    refunded_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ بازپرداخت وجه')
    notes = models.TextField(blank=True, default='', verbose_name='یادداشت')

    class Meta:
        verbose_name = 'تضمین'
        verbose_name_plural = 'تضمین‌ها'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['received_at']),
        ]

    def __str__(self):
        return f"{self.guarantee_type} {self.tracking_code}"


class DamageRecord(models.Model):
    SEVERITY_MINOR = 'MINOR'
    SEVERITY_MODERATE = 'MODERATE'
    SEVERITY_SEVERE = 'SEVERE'
    SEVERITY_CHOICES = (
        (SEVERITY_MINOR, 'جزئی'),
        (SEVERITY_MODERATE, 'متوسط'),
        (SEVERITY_SEVERE, 'شدید'),
    )

    DISPUTE_NONE = 'NONE'
    DISPUTE_OPEN = 'OPEN'
    DISPUTE_RESOLVED = 'RESOLVED'
    DISPUTE_STATUS_CHOICES = (
        (DISPUTE_NONE, 'بدون نزاع'),
        (DISPUTE_OPEN, 'نزاع باز'),
        (DISPUTE_RESOLVED, 'حل شده'),
    )

    reservation = models.ForeignKey(
        'reservations.Reservation', on_delete=models.CASCADE,
        related_name='damage_records', verbose_name='رزرو',
    )
    customer = models.ForeignKey(
        'customers.Customer', on_delete=models.CASCADE,
        related_name='damage_records', verbose_name='مشتری',
    )
    dress = models.ForeignKey(
        'products.Dress', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='damage_records', verbose_name='لباس',
    )
    damage_type = models.CharField(max_length=100, verbose_name='نوع خسارت')
    description = models.TextField(blank=True, default='', verbose_name='شرح')
    severity = models.CharField(
        max_length=20, choices=SEVERITY_CHOICES, null=True, blank=True, verbose_name='شدت خسارت',
    )
    amount = models.BigIntegerField(null=True, blank=True, verbose_name='مبلغ خسارت')
    collected = models.BooleanField(default=False, verbose_name='پرداخت شده')
    payment_reference = models.CharField(max_length=200, null=True, blank=True, verbose_name='کد پیگیری پرداخت')
    related_transaction = models.ForeignKey(
        'financial.Transaction', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='damage_records', verbose_name='تراکنش مرتبط',
    )
    detected_at = models.DateTimeField(auto_now_add=True, verbose_name='شناسایی در')
    detected_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='detected_damages', verbose_name='شناسایی شده توسط',
    )
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_damages', verbose_name='تایید شده توسط',
    )
    dispute_status = models.CharField(
        max_length=20, choices=DISPUTE_STATUS_CHOICES, default=DISPUTE_NONE, verbose_name='وضعیت نزاع',
    )
    dispute_opened_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ باز کردن نزاع')
    dispute_resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ حل نزاع')
    dispute_notes = models.TextField(blank=True, default='', verbose_name='یادداشت نزاع')
    notes = models.TextField(blank=True, default='', verbose_name='یادداشت')

    class Meta:
        verbose_name = 'خسارت'
        verbose_name_plural = 'خسارت‌ها'
        indexes = [
            models.Index(fields=['collected']),
            models.Index(fields=['dispute_status']),
        ]

    def __str__(self):
        return f"خسارت {self.damage_type} رزرو #{self.reservation_id} - {self.amount or 0}"


class CancellationRecord(models.Model):
    REFUND_REQUESTED = 'REQUESTED'
    REFUND_APPROVED = 'APPROVED'
    REFUND_POSTED = 'POSTED'
    REFUND_COMPLETED = 'COMPLETED'
    REFUND_STATUS_CHOICES = (
        (REFUND_REQUESTED, 'درخواست شده'),
        (REFUND_APPROVED, 'تایید شده'),
        (REFUND_POSTED, 'ثبت شده'),
        (REFUND_COMPLETED, 'تکمیل شده'),
    )

    reservation = models.OneToOneField(
        'reservations.Reservation', on_delete=models.CASCADE,
        related_name='cancellation_record', verbose_name='رزرو',
    )
    reason = models.TextField(blank=True, default='', verbose_name='دلیل لغو')
    cancelled_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ لغو')
    cancelled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cancelled_reservations', verbose_name='لغو شده توسط',
    )
    deposit_at_cancel = models.BigIntegerField(null=True, blank=True, verbose_name='بیعانه در زمان لغو')
    refund_amount = models.BigIntegerField(null=True, blank=True, verbose_name='مبلغ بازپرداخت')
    related_transaction = models.ForeignKey(
        'financial.Transaction', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='cancellation_records', verbose_name='تراکنش مرتبط',
    )
    refund_method = models.CharField(
        max_length=20, choices=_LegacyPaymentMethod.CHOICES, null=True, blank=True, verbose_name='روش بازپرداخت',
    )
    refund_posted_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ ثبت بازپرداخت')
    refund_status = models.CharField(
        max_length=20, choices=REFUND_STATUS_CHOICES, default=REFUND_REQUESTED, verbose_name='وضعیت بازپرداخت',
    )
    penalty_amount = models.BigIntegerField(null=True, blank=True, verbose_name='مبلغ جریمه نگه‌داشته‌شده')
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_cancellations', verbose_name='تایید شده توسط',
    )
    approval_date = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ تایید')
    approval_notes = models.TextField(blank=True, default='', verbose_name='یادداشت تایید')
    notes = models.TextField(blank=True, default='', verbose_name='یادداشت')

    class Meta:
        verbose_name = 'رکورد لغو'
        verbose_name_plural = 'رکوردهای لغو'
        indexes = [
            models.Index(fields=['refund_status']),
        ]

    def __str__(self):
        return f"لغو رزرو #{self.reservation_id} — بازپرداخت: {self.refund_amount or 0}"
