import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

import jdatetime
from django.contrib.auth import get_user_model
from customers.models import Customer
from products.models import Dress
from reservations.models import Reservation
from reservations.constants import ReservationStatus, PaymentMethod, GuaranteeType

User = get_user_model()
creator = User.objects.filter(is_superuser=True).first()
if not creator:
    creator = User.objects.first()

customers = list(Customer.objects.all())
dresses = list(Dress.objects.filter(status=Dress.STATUS_ACTIVE))
if not customers or not dresses:
    raise SystemExit('No customers or dresses available to create reservations.')

base_date = jdatetime.date.today()
created = []
for i in range(30):
    customer = customers[i % len(customers)]
    dress = dresses[i % len(dresses)]
    start_date = base_date + jdatetime.timedelta(days=i * 2)

    reservation = Reservation(
        customer=customer,
        dress=dress,
        start_date=start_date,
        rental_days=3,
        deposit_amount=0,
        discount_type=Reservation.DISCOUNT_NONE,
        discount_value=0,
        discount_amount=0,
        final_price=0,
        refunded_amount=0,
        remaining_amount=0,
        payment_method=PaymentMethod.CASH,
        payment_tracking_code=f'TESTPAY{i+1:03}',
        remaining_payment_amount=0,
        remaining_payment_method=PaymentMethod.CASH,
        guarantee1_type=GuaranteeType.CASH,
        guarantee1_tracking_code=f'GT{i+1:03}',
        status=ReservationStatus.CONFIRMED,
        payment_status=Reservation.PAYMENT_UNPAID,
        created_by=creator,
        notes='رزرو تستی برای بررسی صفحه‌بندی و جستجو',
    )
    reservation.save()
    created.append(reservation.pk)

print('Created', len(created), 'reservations:', created)
