# reservations/views.py
from datetime import date
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.dateparse import parse_date
from django.shortcuts import render, get_object_or_404, redirect
import jdatetime
from .utils import parse_reservation_date
from products.models import Dress
from customers.models import Customer
from reservations.models import Reservation
from reservations.forms import (
    ReservationStepOneForm,
    ReservationStepTwoForm,
    ReservationEditForm
)
from .services.availability_service import ReservationAvailabilityService
from .services.change_status import ReservationStatusService
from .constants import ReservationStatus


def can_create_reservation(user):
    if user.is_superuser or getattr(user, "role", None) == "SUPER_ADMIN":
        return True
    return getattr(user, "role", None) in ["SELLER", "MANAGER"]


def can_edit_reservation(user):
    if user.is_superuser or getattr(user, "role", None) == "SUPER_ADMIN":
        return True
    return getattr(user, "role", None) in ["MANAGER"]


def can_delete_reservation(user):
    if user.is_superuser or getattr(user, "role", None) == "SUPER_ADMIN":
        return True
    return getattr(user, "role", None) in ["MANAGER"]


def can_change_reservation_status(user):
    if user.is_superuser or getattr(user, "role", None) == "SUPER_ADMIN":
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
        "can_change_reservation_status": can_change_reservation_status(request.user),
    }

    return render(
        request,
        "reservations/list.html",
        context
    )


@login_required
@require_POST
def reservation_step_one(request):

    if not can_create_reservation(request.user):
        return HttpResponseForbidden()

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

    if not can_create_reservation(request.user):
        return HttpResponseForbidden()

    step1_data = request.session.get("reservation_step1")
    step1_form = None

    if not step1_data:
        step1_form = ReservationStepOneForm(request.POST)
        if not step1_form.is_valid():
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                message = " ".join(
                    [str(e) for errors in step1_form.errors.values() for e in errors]
                )
                return JsonResponse({
                    "success": False,
                    "message": message
                })
            return render(request, "reservations/list.html", {
                "customers": Customer.objects.all(),
                "dresses": Dress.objects.filter(status=Dress.STATUS_ACTIVE),
                "can_create_reservation": can_create_reservation(request.user),
                "can_edit_reservation": can_edit_reservation(request.user),
                "can_delete_reservation": can_delete_reservation(request.user),
                "step1_errors": step1_form.errors
            })

        cleaned = step1_form.cleaned_data
        step1_data = {
            "customer_id": cleaned["customer"].id,
            "dress_id": cleaned["dress"].id,
            "start_date": str(cleaned["start_date"]),
            "rental_days": cleaned["rental_days"],
            "end_date": str(cleaned["end_date"]),
            "event_date": str(getattr(cleaned["customer"], "ceremony_date", "")) if getattr(cleaned["customer"], "ceremony_date", None) else None,
        }

    form = ReservationStepTwoForm(request.POST)
    if not form.is_valid():
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            message = " ".join(
                [str(e) for errors in form.errors.values() for e in errors]
            )
            return JsonResponse({
                "success": False,
                "message": message
            })
        return render(request, "reservations/list.html", {
            "customers": Customer.objects.all(),
            "dresses": Dress.objects.filter(status=Dress.STATUS_ACTIVE),
            "can_create_reservation": can_create_reservation(request.user),
            "can_edit_reservation": can_edit_reservation(request.user),
            "can_delete_reservation": can_delete_reservation(request.user),
            "step2_errors": form.errors
        })

    try:
        start_date = parse_reservation_date(step1_data["start_date"])
        if start_date is None:
            raise ValueError("Invalid start date")
        rental_days = int(step1_data["rental_days"])
    except Exception:
        return JsonResponse({
            "success": False,
            "message": "اطلاعات رزرو نامعتبر است."
        })

    try:
        with transaction.atomic():
            customer = Customer.objects.get(id=step1_data["customer_id"])
            dress = Dress.objects.select_for_update().get(id=step1_data["dress_id"])

            end_date = ReservationAvailabilityService.calculate_end_date(start_date, rental_days)
            blocking_statuses = ReservationAvailabilityService.get_blocking_statuses()

            overlapping_reservations = Reservation.objects.select_for_update().filter(
                dress=dress,
                status__in=blocking_statuses,
                start_date__lt=end_date,
                end_date__gt=start_date
            )

            if overlapping_reservations.exists():
                return JsonResponse({
                    "success": False,
                    "message": "این لباس در این بازه زمانی رزرو شده است."
                })

            reservation = form.save(commit=False)
            reservation.customer = customer
            reservation.dress = dress
            reservation.start_date = start_date
            reservation.rental_days = rental_days
            reservation.end_date = end_date
            reservation.event_date = getattr(customer, "ceremony_date", None)
            reservation.rent_price = dress.daily_rent_price
            reservation.status = ReservationStatus.CONFIRMED
            reservation.created_by = request.user
            reservation.save()

    except Dress.DoesNotExist:
        return JsonResponse({
            "success": False,
            "message": "لباس انتخابی یافت نشد."
        })

    if "reservation_step1" in request.session:
        del request.session["reservation_step1"]

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "success": True,
            "message": "رزرو با موفقیت ثبت شد."
        })

    return redirect("reservations:list")


@login_required
@require_POST
def reservation_mark_delivered(request, pk):

    if not can_change_reservation_status(request.user):
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    try:
        ReservationStatusService.change_status(
            reservation,
            ReservationStatus.DELIVERED,
            request.user
        )
    except ValueError:
        return JsonResponse({
            "success": False,
            "message": "این تغییر وضعیت مجاز نیست."
        }, status=400)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True})

    return redirect("reservations:list")


@login_required
@require_POST
def reservation_mark_returned(request, pk):

    if not can_change_reservation_status(request.user):
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    try:
        ReservationStatusService.change_status(
            reservation,
            ReservationStatus.RETURNED,
            request.user
        )
    except ValueError:
        return JsonResponse({
            "success": False,
            "message": "این تغییر وضعیت مجاز نیست."
        }, status=400)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True})

    return redirect("reservations:list")


@login_required
@require_POST
def reservation_mark_laundry(request, pk):

    if not can_change_reservation_status(request.user):
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    try:
        ReservationStatusService.change_status(
            reservation,
            ReservationStatus.LAUNDRY,
            request.user
        )
    except ValueError:
        return JsonResponse({
            "success": False,
            "message": "این تغییر وضعیت مجاز نیست."
        }, status=400)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True})

    return redirect("reservations:list")


@login_required
@require_POST
def reservation_mark_ready(request, pk):

    if not can_change_reservation_status(request.user):
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    try:
        ReservationStatusService.change_status(
            reservation,
            ReservationStatus.READY,
            request.user
        )
    except ValueError:
        return JsonResponse({
            "success": False,
            "message": "این تغییر وضعیت مجاز نیست."
        }, status=400)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True})

    return redirect("reservations:list")


@login_required
@require_POST
def reservation_finalize_delivery(request, pk):

    if not can_change_reservation_status(request.user):
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    try:
        ReservationStatusService.change_status(
            reservation,
            ReservationStatus.DELIVERED,
            request.user
        )
    except ValueError as e:
        error_message = str(e) or "این رزرو آماده برای تحویل نیست."
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({
                "success": False,
                "message": error_message
            }, status=400)

        messages.error(request, error_message)
        return redirect("reservations:list")

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "success": True,
            "message": "لباس با موفقیت تحویل شد."
        })

    messages.success(request, "لباس با موفقیت تحویل شد.")
    return redirect("reservations:list")


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

    if not can_edit_reservation(request.user):
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    locked_statuses = [
        ReservationStatus.DELIVERED,
        ReservationStatus.RETURNED,
        ReservationStatus.LAUNDRY,
        ReservationStatus.READY,
        ReservationStatus.CANCELLED
    ]

    if reservation.status in locked_statuses:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({
                "success": False,
                "errors": {"__all__": ["اطلاعات پرداخت بعد از تحویل قابل تغییر نیست."]}
            })
        return redirect("reservations:list")

    form = ReservationEditForm(
        request.POST,
        instance=reservation,
        original_dress=reservation.dress,
        original_start_date=reservation.start_date,
        original_rental_days=reservation.rental_days,
        reservation_id=reservation.id
    )

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

    if not can_delete_reservation(request.user):
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    try:
        ReservationStatusService.change_status(
            reservation,
            ReservationStatus.CANCELLED,
            request.user
        )
    except ValueError as exc:
        error_message = str(exc) or "این رزرو در وضعیت حاضر قابل لغو نیست."
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({
                "success": False,
                "message": error_message
            }, status=400)

        messages.error(request, error_message)
        return redirect("reservations:list")

    success_message = "رزرو با موفقیت لغو شد."
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "success": True,
            "message": success_message
        })

    messages.success(request, success_message)
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
