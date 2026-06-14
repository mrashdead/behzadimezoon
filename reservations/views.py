# reservations/views.py
from datetime import date
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_date
from django.shortcuts import render, get_object_or_404, redirect
import jdatetime
from .utils import parse_reservation_date
from products.models import Dress
from customers.models import Customer
from reservations.models import Reservation
from reservations.forms import (
    ReservationStepOneForm,
    ReservationStepTwoForm
)
from .services.availability_service import ReservationAvailabilityService
from .services.change_status import ReservationStatusService
from .constants import ReservationStatus


def can_create_reservation(user):
    if user.is_superuser:
        return True
    return getattr(user, "role", None) in ["SELLER", "MANAGER"]


def can_edit_reservation(user):
    if user.is_superuser:
        return True
    return getattr(user, "role", None) in ["MANAGER"]


def can_delete_reservation(user):
    if user.is_superuser:
        return True
    return getattr(user, "role", None) in ["MANAGER"]


@login_required
def reservation_list(request):

    reservations = Reservation.objects.select_related(
        "customer",
        "dress"
    ).all()

    context = {
        "reservations": reservations,
        "customers": Customer.objects.all(),
        "dresses": Dress.objects.filter(status=Dress.STATUS_ACTIVE),
        "can_create_reservation": can_create_reservation(request.user),
        "can_edit_reservation": can_edit_reservation(request.user),
        "can_delete_reservation": can_delete_reservation(request.user),
    }

    return render(
        request,
        "reservations/list.html",
        context
    )


@login_required
@require_POST
def reservation_step_one(request):

    form = ReservationStepOneForm(request.POST)

    if not form.is_valid():

        return JsonResponse({
            "success": False,
            "errors": form.errors
        })

    customer = form.cleaned_data["customer"]
    dress = form.cleaned_data["dress"]
    start_date = form.cleaned_data["start_date"]
    rental_days = form.cleaned_data["rental_days"]
    end_date = form.cleaned_data["end_date"]

    event_date = getattr(customer, "ceremony_date", None)

    rent_price = dress.daily_rent_price

    request.session["reservation_step1"] = {
        "customer_id": customer.id,
        "dress_id": dress.id,
        "start_date": str(start_date),
        "rental_days": rental_days,
        "end_date": str(end_date),
        "event_date": str(event_date) if event_date else None,
        "rent_price": rent_price
    }

    return JsonResponse({
        "success": True,
        "end_date": str(end_date),
        "event_date": str(event_date) if event_date else None,
        "rent_price": rent_price
    })


@login_required
@require_POST
def reservation_create(request):

    step1_data = request.session.get("reservation_step1")

    if not step1_data:
        return JsonResponse({
            "success": False,
            "message": "مرحله اول کامل نشده است."
        })

    form = ReservationStepTwoForm(request.POST)

    if not form.is_valid():

        return JsonResponse({
            "success": False,
            "errors": form.errors
        })

    reservation = form.save(commit=False)

    reservation.customer_id = step1_data["customer_id"]
    reservation.dress_id = step1_data["dress_id"]

    reservation.start_date = parse_date(step1_data["start_date"])
    reservation.rental_days = step1_data["rental_days"]
    reservation.end_date = parse_date(step1_data["end_date"])
    reservation.event_date = parse_date(step1_data["event_date"]) if step1_data["event_date"] else None

    reservation.rent_price = step1_data["rent_price"]

    reservation.created_by = request.user

    reservation.save()

    del request.session["reservation_step1"]

    return JsonResponse({
        "success": True,
        "message": "رزرو با موفقیت ثبت شد."
    })


@login_required
def reservation_detail(request, pk):

    reservation = get_object_or_404(Reservation, pk=pk)

    return render(
        request,
        "reservations/partials/_detail_modal.html",
        {"reservation": reservation}
    )


@login_required
@require_POST
def reservation_edit(request, pk):

    reservation = get_object_or_404(Reservation, pk=pk)
    form = ReservationStepTwoForm(request.POST, instance=reservation)

    if not form.is_valid():
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({
                "success": False,
                "errors": form.errors
            })
        return redirect("reservations:list")

    reservation = form.save(commit=False)
    reservation.updated_by = request.user
    reservation.save()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "success": True,
            "message": "رزرو با موفقیت به‌روز شد."
        })

    return redirect("reservations:list")


@login_required
@require_POST
def reservation_delete(request, pk):

    reservation = get_object_or_404(Reservation, pk=pk)
    ReservationStatusService.change_status(
        reservation,
        ReservationStatus.CANCELLED,
        request.user
    )

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "success": True
        })

    return redirect("reservations:list")



@login_required
@require_POST
def check_availability(request):

    dress_id = request.POST.get("dress_id")
    start_date = request.POST.get("start_date")
    rental_days = request.POST.get("rental_days")

    if not all([dress_id, start_date, rental_days]):
        return JsonResponse({
            "success": False,
            "message": "اطلاعات ناقص است."
        })

    customer_id = request.POST.get("customer_id")

    try:
        dress = Dress.objects.get(id=dress_id)
        rental_days = int(rental_days)
    except:
        return JsonResponse({
            "success": False,
            "message": "اطلاعات نامعتبر است."
        })

    start_date_obj = parse_reservation_date(start_date)

    if start_date_obj is None:
        return JsonResponse({
            "success": False,
            "message": "تاریخ نامعتبر است."
        })

    customer = None
    event_date = None
    if customer_id:
        try:
            customer = Customer.objects.get(id=customer_id)
            event_date = getattr(customer, "ceremony_date", None)
        except Customer.DoesNotExist:
            event_date = None

    is_available, end_date = ReservationAvailabilityService.is_dress_available(
        dress=dress,
        start_date=start_date_obj,
        rental_days=rental_days
    )

    if is_available:
        return JsonResponse({
            "success": True,
            "available": True,
            "end_date": end_date.isoformat() if end_date else None,
            "rent_price": str(dress.daily_rent_price),
            "event_date": event_date.isoformat() if event_date else None
        })

    return JsonResponse({
        "success": True,
        "available": False,
        "message": "این لباس در این بازه زمانی رزرو شده است."
    })
