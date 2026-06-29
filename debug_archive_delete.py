import os
import django
import traceback
import uuid
import jdatetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from accounts.models import User
from customers.models import Customer
from products.models import Dress
from reservations.models import Reservation
from reservations.constants import ReservationStatus
from financial.models import Transaction
from reservations.services.archive_service import ReservationArchiveService

unique_suffix = uuid.uuid4().hex[:8]
admin = User.objects.create_user(f'temp_admin_{unique_suffix}', password='password123', is_superuser=True, is_staff=True)
customer = Customer.objects.create(
    bride_first_name='A',
    bride_last_name='B',
    bride_phone=f'0912{unique_suffix[:7]}',
    ceremony_date=jdatetime.date(1402, 1, 1),
    how_to_know='test',
    allow_contact=True
)
dress = Dress.objects.create(code=f'D{unique_suffix.upper()}', daily_rent_price=100000)
reservation = Reservation.objects.create(
    customer=customer,
    dress=dress,
    start_date=jdatetime.date(1402, 1, 1),
    rental_days=3,
    status=ReservationStatus.ARCHIVED,
    previous_status=ReservationStatus.CONFIRMED,
    archived_at=jdatetime.datetime(1402, 1, 5, 12, 0, 0),
    archived_by=admin,
    rent_price=dress.daily_rent_price,
    deposit_amount=50000,
    discount_amount=0,
    final_price=100000,
    remaining_amount=50000,
    payment_method='CASH',
    payment_tracking_code='PAY123',
    guarantee1_type='CASH',
    guarantee1_tracking_code='G1',
    created_by=admin
)
transaction = Transaction.objects.create(
    reservation=reservation,
    amount=100000,
    type=Transaction.Type.PAYMENT,
    created_by=admin
)
print('created', reservation.pk, transaction.pk)
try:
    ReservationArchiveService.create_snapshot_and_delete(reservation, admin)
    print('success')
except Exception:
    traceback.print_exc()
