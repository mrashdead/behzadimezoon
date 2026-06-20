from reservations.constants import ReservationStatus


class PaymentGuardService:
    @staticmethod
    def verify_payment_for_delivery(reservation):
        """
        Verify that remaining balance is settled before delivery.
        Balance is considered settled if:
        1. remaining_amount is already 0 (deposit covered full cost), OR
        2. remaining_payment_amount is set (payment being registered now)
        """
        if reservation.remaining_amount == 0:
            return True

        if reservation.remaining_payment_amount and reservation.remaining_payment_amount > 0:
            return True

        raise ValueError(
            f"باقی‌مانده باید صفر باشد. لطفا ابتدا تمام وجوه را دریافت کنید. "
            f"(باقی‌مانده: {reservation.remaining_amount} تومان)"
        )

