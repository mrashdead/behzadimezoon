from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from financial.forms import GuaranteeForm, DamageForm, TransactionForm, CancellationForm
from financial.services.guarantee_service import GuaranteeService
from financial.services.damage_service import DamageService
from financial.services.transaction_service import TransactionService
from financial.models import Guarantee, DamageRecord, CancellationRecord


def _user_is_allowed(user, reservation):
    # mirror reservations permission: sellers can only act on own reservations
    if getattr(user, 'role', None) == 'SELLER':
        return reservation.created_by_id == user.pk
    return True


@login_required
def reservation_financial_view(request, pk):
    from reservations.models import Reservation
    reservation = get_object_or_404(Reservation, pk=pk)
    if not _user_is_allowed(request.user, reservation):
        return JsonResponse({'error': 'دسترسی ندارید'}, status=403)

    transactions = reservation.transactions.select_related('created_by').all()
    guarantees = reservation.guarantees.all()
    damages = reservation.damage_records.all()
    cancellation = getattr(reservation, 'cancellation_record', None)

    totals = {
        'total_received': TransactionService.reservation_cash_inflow(reservation),
        'final_price': reservation.final_price or 0,
        'deposit': reservation.deposit_amount or 0,
        'remaining': reservation.remaining_amount or 0,
    }

    return render(request, 'financial/partials/_reservation_financial.html', {
        'reservation': reservation,
        'transactions': transactions,
        'guarantees': guarantees,
        'damages': damages,
        'cancellation': cancellation,
        'totals': totals,
        'guarantee_form': GuaranteeForm(),
        'damage_form': DamageForm(),
        'transaction_form': TransactionForm(),
        'cancellation_form': CancellationForm(),
    })


@login_required
@require_POST
def add_guarantee_view(request, pk):
    from reservations.models import Reservation
    reservation = get_object_or_404(Reservation, pk=pk)
    if not _user_is_allowed(request.user, reservation):
        return JsonResponse({'error': 'دسترسی ندارید'}, status=403)

    form = GuaranteeForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'error': form.errors}, status=400)

    data = form.cleaned_data
    guarantee = GuaranteeService.create_guarantee(
        reservation=reservation,
        customer=reservation.customer,
        tracking_code=data['tracking_code'],
        guarantee_type=data['guarantee_type'],
        estimated_value=data.get('estimated_value'),
        notes=data.get('notes')
    )
    return JsonResponse({'result': 'ok', 'guarantee_id': guarantee.pk, 'message': 'تضمین با موفقیت ثبت شد.'})


@login_required
@require_POST
def return_guarantee_view(request, pk):
    guarantee = get_object_or_404(Guarantee, pk=pk)
    reservation = guarantee.reservation
    if not _user_is_allowed(request.user, reservation):
        return JsonResponse({'error': 'دسترسی ندارید'}, status=403)

    guarantee.status = Guarantee.RETURNED
    guarantee.returned_at = None
    guarantee.save()
    return JsonResponse({'result': 'ok', 'message': 'تضمین علامت‌گذاری شد: بازگردانده‌شده.'})


@login_required
@require_POST
def add_damage_view(request, pk):
    from reservations.models import Reservation
    reservation = get_object_or_404(Reservation, pk=pk)
    if not _user_is_allowed(request.user, reservation):
        return JsonResponse({'error': 'دسترسی ندارید'}, status=403)

    form = DamageForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'error': form.errors}, status=400)

    data = form.cleaned_data
    dr = DamageService.record_damage(
        reservation=reservation,
        customer=reservation.customer,
        damage_type=data['damage_type'],
        amount=data.get('amount'),
        description=data.get('description'),
        created_by=request.user
    )
    return JsonResponse({'result': 'ok', 'damage_id': dr.pk, 'message': 'خسارت ثبت شد.'})


@login_required
@require_POST
def create_transaction_view(request, pk):
    from reservations.models import Reservation
    reservation = get_object_or_404(Reservation, pk=pk)
    if not _user_is_allowed(request.user, reservation):
        return JsonResponse({'error': 'دسترسی ندارید'}, status=403)

    form = TransactionForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'error': form.errors}, status=400)

    data = form.cleaned_data
    tx_type = data['type']
    amount = data['amount']
    payment_method = data.get('payment_method')
    external = data.get('external_reference')
    note = data.get('note')

    # Map to TransactionService helpers
    if tx_type == 'DEPOSIT':
        tx = TransactionService.create_deposit(reservation=reservation, amount=amount, created_by=request.user, payment_method=payment_method, external_reference=external, note=note)
    elif tx_type == 'FINAL_PAYMENT':
        tx = TransactionService.create_final_payment(reservation=reservation, amount=amount, created_by=request.user, payment_method=payment_method, external_reference=external, note=note)
    elif tx_type == 'REFUND':
        tx = TransactionService.create_refund(reservation=reservation, amount=amount, created_by=request.user, payment_method=payment_method, external_reference=external, note=note)
    else:
        tx = TransactionService.create(reservation=reservation, transaction_type=tx_type, amount=amount, created_by=request.user, payment_method=payment_method, external_reference=external, note=note)

    return JsonResponse({'result': 'ok', 'transaction_id': tx.pk, 'message': 'تراکنش با موفقیت ثبت شد.'})


@login_required
@require_POST
def cancel_reservation_flow(request, pk):
    from reservations.models import Reservation
    reservation = get_object_or_404(Reservation, pk=pk)
    if not _user_is_allowed(request.user, reservation):
        return JsonResponse({'error': 'دسترسی ندارید'}, status=403)

    form = CancellationForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'error': form.errors}, status=400)

    data = form.cleaned_data
    # create CancellationRecord
    cr = CancellationRecord.objects.create(
        reservation=reservation,
        reason=data.get('reason', ''),
        deposit_at_cancel=reservation.deposit_amount or 0,
        refund_amount=data.get('refund_amount') or 0,
        penalty_amount=data.get('penalty_amount') or 0,
        notes=data.get('notes', '')
    )

    # Create refund transaction if refund_amount > 0
    if cr.refund_amount and cr.refund_amount > 0:
        TransactionService.create_refund(reservation=reservation, amount=cr.refund_amount, created_by=request.user, note='بازپرداخت در لغو رزرو')

    # Create cancellation fee as accrual if penalty_amount > 0
    if cr.penalty_amount and cr.penalty_amount > 0:
        TransactionService.create_cancellation_fee(reservation=reservation, amount=cr.penalty_amount, created_by=request.user, note='جریمه لغو ثبت‌شده')

    return JsonResponse({'result': 'ok', 'cancellation_id': cr.pk, 'message': 'لغو رزرو ثبت شد.'})
