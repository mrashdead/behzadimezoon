import os
import sys
# Ensure project root is on path when running standalone
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()
from django.test import Client
from accounts.models import User
from customers.models import Customer
from products.models import Dress
from django.contrib.sessions.models import Session
import jdatetime

# Create objects if not existing
customer, _ = Customer.objects.get_or_create(bride_first_name='DBG', bride_last_name='DBG', bride_phone='09120000001')
dress, _ = Dress.objects.get_or_create(code='DBG1', defaults={'daily_rent_price': 100000})
user, _ = User.objects.get_or_create(username='dbg_manager')
user.set_password('password123')
user.role = 'MANAGER'
user.save()

c = Client()
logged = c.login(username='dbg_manager', password='password123')
print('logged in:', logged)

session = c.session
session['reservation_step1'] = {
    'customer_id': customer.id,
    'dress_id': dress.id,
    'start_date': '1402/01/01',
    'rental_days': 3,
    'rent_price': dress.daily_rent_price,
}
session.save()
print('client.session keys after save:', list(c.session.keys()))
print('session_key cookie:', c.cookies.get('sessionid'))

sk = c.session.session_key
print('session_key:', sk)

try:
    s = Session.objects.get(session_key=sk)
    print('stored session decode keys:', s.get_decoded().keys())
    print('stored reservation_step1:', s.get_decoded().get('reservation_step1'))
except Session.DoesNotExist:
    print('No Session with key in DB')

print('done')
