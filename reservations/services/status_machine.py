from reservations.models import Reservation


RESERVATION_TRANSITIONS = {
    Reservation.Status.DRAFT: {
        Reservation.Status.CONFIRMED,
        Reservation.Status.CANCELED,
    },
    Reservation.Status.CONFIRMED: {
        Reservation.Status.DELIVERED,
        Reservation.Status.CANCELED,
    },
    Reservation.Status.DELIVERED: {
        Reservation.Status.RETURNED,
    },
    Reservation.Status.RETURNED: {
        Reservation.Status.LAUNDRY,
    },
    Reservation.Status.LAUNDRY: set(),
    Reservation.Status.CANCELED: set(),
}


def can_transition(current_status, new_status):
    """
    فقط مجاز بودن مسیر وضعیت را بررسی می‌کند.
    این تابع کاری با نقش کاربر ندارد.
    """
    return new_status in RESERVATION_TRANSITIONS.get(current_status, set())


def get_available_transitions(current_status):
    """
    وضعیت‌های بعدی مجاز را برمی‌گرداند.
    """
    return list(RESERVATION_TRANSITIONS.get(current_status, set()))


def validate_transition(current_status, new_status):
    """
    اگر تغییر وضعیت غیرمجاز باشد Exception می‌دهد.
    """
    if current_status == new_status:
        return

    if not can_transition(current_status, new_status):
        raise ValueError(
            f'تغییر وضعیت از "{current_status}" به "{new_status}" مجاز نیست.'
        )


def can_change_status(user, reservation, new_status):
    """
    تابع سازگار با نسخه قبلی پروژه.
    این تابع هم transition را چک می‌کند، هم سطح دسترسی کاربر را.

    change_status.py فعلاً این تابع را import می‌کند؛
    پس وجود این تابع برای رفع ImportError ضروری است.
    """

    if not user or not user.is_authenticated:
        return False

    current_status = reservation.status

    if current_status == new_status:
        return True

    if not can_transition(current_status, new_status):
        return False

    # اگر superuser جنگو بود
    if getattr(user, 'is_superuser', False):
        return True

    # اگر پروژه role سفارشی دارد
    role = getattr(user, 'role', None)

    # مدیر کل و مدیر اجازه همه transitionهای مجاز را دارند
    if role in ['SUPER_ADMIN', 'MANAGER']:
        return True

    # فروشنده دسترسی محدودتر دارد
    if role == 'SELLER':
        return _seller_can_change_status(reservation, new_status)

    return False


def _seller_can_change_status(reservation, new_status):
    """
    قوانین دسترسی فروشنده.
    این بخش را می‌توانی دقیقاً مطابق سیاست مزون تغییر بدهی.
    """

    # فروشنده بتواند پیش‌نویس را تایید یا لغو کند
    if reservation.status == Reservation.Status.DRAFT:
        return new_status in {
            Reservation.Status.CONFIRMED,
            Reservation.Status.CANCELED,
        }

    # فروشنده بتواند رزرو تایید شده را تحویل دهد
    if reservation.status == Reservation.Status.CONFIRMED:
        return new_status == Reservation.Status.DELIVERED

    # فروشنده بتواند لباس تحویل‌شده را برگشت بزند
    if reservation.status == Reservation.Status.DELIVERED:
        return new_status == Reservation.Status.RETURNED

    return False
