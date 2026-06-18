from reservations.constants import ReservationStatus


class PaymentGuardService:
    @staticmethod
    def verify_payment_for_delivery(reservation):
        if reservation.remaining_amount > 0:
            raise ValueError(
                f"باقی‌مانده باید صفر باشد. لطفا ابتدا تمام وجوه را دریافت کنید. "
                f"(باقی‌مانده: {reservation.remaining_amount} تومان)"
            )
        return True
