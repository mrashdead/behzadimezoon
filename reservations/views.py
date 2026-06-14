# reservations/views.py

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_date
from products.models import Dress
from .services.availability_service import ReservationAvailabilityService
from django.shortcuts import render, get_object_or_404
from reservations.models import Reservation
from reservations.forms import (
    ReservationStepOneForm,
    ReservationStepTwoForm
)

from reservations.services.availability_service import ReservationAvailabilityService


@login_required
def reservation_list(request):

    reservations = Reservation.objects.select_related(
        "customer",
        "dress"
    ).all()

    context = {
        "reservations": reservations
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

    event_date = getattr(customer, "event_date", None)

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
        "end_date": end_date,
        "event_date": event_date,
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

    reservation.start_date = step1_data["start_date"]
    reservation.rental_days = step1_data["rental_days"]
    reservation.end_date = step1_data["end_date"]
    reservation.event_date = step1_data["event_date"]

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
        "reservations/ui/partials/_detail_modal.html",
        {"reservation": reservation}
    )


@login_required
@require_POST
def reservation_delete(request, pk):

    reservation = get_object_or_404(Reservation, pk=pk)

    reservation.status = "CANCELLED"
    reservation.updated_by = request.user
    reservation.save()

    return JsonResponse({
        "success": True
    })


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

    try:
        dress = Dress.objects.get(id=dress_id)
        start_date = parse_date(start_date)
        rental_days = int(rental_days)
    except:
        return JsonResponse({
            "success": False,
            "message": "اطلاعات نامعتبر است."
        })

    is_available, end_date = ReservationAvailabilityService.is_dress_available(
        dress=dress,
        start_date=start_date,
        rental_days=rental_days
    )

    if is_available:
        return JsonResponse({
            "success": True,
            "available": True,
            "end_date": end_date
        })

    return JsonResponse({
        "success": True,
        "available": False,
        "message": "این لباس در این بازه زمانی رزرو شده است."
    })
