from reservations.constants import ReservationStatus


class PaymentGuardService:
    @staticmethod
    def has_paid_deposit(reservation):
        """
        آیا برای رزرو حداقل یک بیعانه معتبر پرداخت شده است؟

        مقدار ``deposit_amount`` یک کش مشتق‌شده از مجموع تراکنش‌های معتبر
        بیعانه است (توسط ``ReservationPaymentService`` همگام می‌شود)، بنابراین
        این بررسی بدون کوئری اضافه و بر پایه پرداخت‌های واقعی انجام می‌شود.
        """
        if (reservation.deposit_amount or 0) > 0:
            return True
        # برای اطمینان، در صورت ناهمگامی کش، از منبع اصلی محاسبه می‌کنیم
        from reservations.services.payment_stage_service import ReservationPaymentService
        return ReservationPaymentService.total_deposit(reservation) > 0

    @staticmethod
    def verify_payment_for_delivery(reservation):
        """
        بررسی می‌کند که پیش از تحویل، مانده حساب رزرو تسویه شده باشد.

        تنها معیار مجازبودن تحویل این است که **مانده واقعی** (بر پایه مجموع
        پرداخت‌های معتبر منهای بازپرداخت‌ها) صفر یا کمتر باشد. پیش‌تر وجود
        مقدار در ``remaining_payment_amount`` به‌تنهایی تحویل را مجاز می‌کرد
        که یک حفره امنیتی مالی بود (تحویل با پرداخت جزئی یا حتی بدون پرداخت).
        """
        from reservations.services.payment_stage_service import ReservationPaymentService

        remaining = ReservationPaymentService.core_remaining_amount(reservation)

        if remaining <= 0:
            return True

        raise ValueError(
            f"باقی‌مانده باید صفر باشد. لطفا ابتدا تمام وجوه را دریافت کنید. "
            f"(باقی‌مانده: {remaining:,} تومان)"
        )
