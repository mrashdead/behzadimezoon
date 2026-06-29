# reservations/views.py
from datetime import date
from datetime import timedelta
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from django.shortcuts import render, get_object_or_404, redirect
import jdatetime
from .utils import parse_reservation_date, get_reservations_for_user, date_to_iso
from products.models import Dress
from customers.models import Customer
from reservations.models import Reservation
from reservations.forms import (
    ReservationStepOneForm,
    ReservationStepTwoForm,
    ReservationEditForm,
    RemainingPaymentForm,
    DamageReturnForm
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


def user_owns_reservation(user, reservation):
    """Check if user owns the reservation (created it)."""
    return reservation.created_by_id == user.id



@login_required
def reservation_list(request):

    # Filter reservations based on user role and hide archived items from the active list.
    reservations = get_reservations_for_user(request.user).select_related(
        "customer",
        "dress"
    ).exclude(status=ReservationStatus.ARCHIVED)

    # Avoid selecting newly added DB columns until migrations are applied
    # This prevents template rendering errors when the DB schema is not migrated yet.
    reservations = reservations.defer('discount_type', 'discount_value', 'discount_amount', 'refunded_amount')

    context = {
        "reservations": reservations,
        "customers": Customer.objects.all(),
        "dresses": Dress.objects.filter(status=Dress.STATUS_ACTIVE),
        "can_create_reservation": can_create_reservation(request.user),
        "can_edit_reservation": can_edit_reservation(request.user),
        "can_delete_reservation": can_delete_reservation(request.user),
        "can_change_reservation_status": can_change_reservation_status(request.user),
        "damage_return_form": DamageReturnForm(),
    }

    return render(
        request,
        "reservations/list.html",
        context
    )


@login_required
def reservation_archive_list(request):
    reservations = get_reservations_for_user(request.user).select_related(
        "customer",
        "dress"
    ).filter(status=ReservationStatus.ARCHIVED)

    reservations = reservations.defer('discount_type', 'discount_value', 'discount_amount', 'refunded_amount')

    context = {
        "reservations": reservations,
        "page_title": "آرشیو رزروها",
        "archive_mode": True,
        "can_create_reservation": can_create_reservation(request.user),
        "can_edit_reservation": False,
        "can_delete_reservation": False,
        "can_change_reservation_status": False,
        "can_restore_reservation": request.user.is_superuser,
        "damage_return_form": DamageReturnForm(),
    }

    return render(
        request,
        "reservations/archive_list.html",
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
        "rent_price": rent_price,
    }

    return JsonResponse({
        "success": True,
        "end_date": str(end_date),
        "event_date": date_to_iso(event_date),
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
        rent_price = cleaned["dress"].daily_rent_price
        step1_data = {
            "customer_id": cleaned["customer"].id,
            "dress_id": cleaned["dress"].id,
            "start_date": str(cleaned["start_date"]),
            "rental_days": cleaned["rental_days"],
            "end_date": str(cleaned["end_date"]),
            "event_date": date_to_iso(getattr(cleaned["customer"], "ceremony_date", None)),
            "rent_price": rent_price,
        }

    rent_price = None
    if step1_data:
        rent_price = step1_data.get("rent_price")
        if rent_price is not None:
            try:
                rent_price = int(rent_price)
            except (TypeError, ValueError):
                rent_price = None

    if rent_price is None and step1_data and step1_data.get("dress_id"):
        try:
            rent_price = Dress.objects.get(id=step1_data["dress_id"]).daily_rent_price
        except Dress.DoesNotExist:
            rent_price = None

    form = ReservationStepTwoForm(request.POST, rent_price=rent_price)
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
            # Minimal duplicate-submit protection: if an identical reservation
            # (same customer, dress, start/end dates) was created by the same
            # user in the very recent past, treat the request as idempotent.
            recent_threshold = timezone.now() - timedelta(seconds=5)
            already = Reservation.objects.filter(
                customer=customer,
                dress=dress,
                start_date=start_date,
                end_date=end_date,
                created_by=request.user,
                created_at__gte=recent_threshold
            ).exists()

            if already:
                # Return success to client to avoid duplicate UI actions.
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse({"success": True, "message": "رزرو قبلا ثبت شد."})
                return redirect("reservations:list")

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

    if request.user.role == "SELLER":
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
def reservation_mark_returned(request, pk):

    if not can_change_reservation_status(request.user):
        return HttpResponseForbidden()

    if request.user.role == "SELLER":
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    # GET request: Show the damage form inside the modal
    if request.method == "GET":
        form = DamageReturnForm()
        return render(
            request,
            "reservations/partials/_damage_return_modal.html",
            {
                "form": form,
                "reservation": reservation
            }
        )

    # POST request: Process the damage form and change status
    form = DamageReturnForm(request.POST)

    if not form.is_valid():
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({
                "success": False,
                "errors": form.errors
            }, status=400)

        return render(
            request,
            "reservations/partials/_damage_return_modal.html",
            {
                "form": form,
                "reservation": reservation,
                "errors": form.errors
            }
        )

    # Save damage information
    item_damaged = form.cleaned_data.get("item_damaged")
    damage_amount = form.cleaned_data.get("damage_amount")
    damage_notes = form.cleaned_data.get("damage_notes")

    reservation.item_damaged = item_damaged
    reservation.damage_amount = damage_amount if item_damaged and damage_amount and damage_amount > 0 else None
    reservation.damage_notes = damage_notes or ""

    try:
        ReservationStatusService.change_status(
            reservation,
            ReservationStatus.RETURNED,
            request.user
        )
    except ValueError:
        error_msg = "این تغییر وضعیت مجاز نیست."
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({
                "success": False,
                "message": error_msg
            }, status=400)

        messages.error(request, error_msg)
        return redirect("reservations:list")

    success_msg = "بازگشت لباس با موفقیت ثبت شد."
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "success": True,
            "message": success_msg
        })

    messages.success(request, success_msg)
    return redirect("reservations:list")


@login_required
@require_POST
def reservation_mark_laundry(request, pk):

    if not can_change_reservation_status(request.user):
        return HttpResponseForbidden()

    if request.user.role == "SELLER":
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

    if request.user.role == "SELLER":
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

    if request.user.role == "SELLER":
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    form = RemainingPaymentForm(request.POST)

    if not form.is_valid():
        error_message = " ".join(
            [str(e) for errors in form.errors.values() for e in errors]
        )
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({
                "success": False,
                "errors": form.errors
            }, status=400)

        messages.error(request, error_message)
        return redirect("reservations:list")

    amount = form.cleaned_data.get("remaining_payment_amount")
    method = form.cleaned_data.get("remaining_payment_method")
    code = form.cleaned_data.get("remaining_payment_tracking_code")

    if amount and amount > 0:
        try:
            form.validate_payment_amount(reservation.remaining_amount)
        except ValidationError as e:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({
                    "success": False,
                    "errors": {"remaining_payment_amount": [str(e)]}
                }, status=400)

            messages.error(request, str(e))
            return redirect("reservations:list")

        reservation.remaining_payment_amount = amount
        reservation.remaining_payment_method = method
        reservation.remaining_payment_tracking_code = code
        reservation.remaining_paid_at = timezone.now()
        reservation.remaining_amount = 0
        reservation.save()

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

    # Sellers can only see their own reservations
    if request.user.role == "SELLER" and not user_owns_reservation(request.user, reservation):
        return HttpResponseForbidden()

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

    # Sellers cannot edit (manager-only operation)
    # Extra protection: sellers trying to tamper with URL
    if request.user.role == "SELLER":
        return HttpResponseForbidden()

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
def reservation_archive(request, pk):

    if not can_delete_reservation(request.user):
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    # Sellers cannot archive (manager-only operation)
    if request.user.role == "SELLER":
        return HttpResponseForbidden()

    try:
        ReservationStatusService.change_status(
            reservation,
            ReservationStatus.ARCHIVED,
            request.user
        )
    except ValueError as exc:
        error_message = str(exc) or "این رزرو در وضعیت حاضر قابل آرشیو نیست."
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({
                "success": False,
                "message": error_message
            }, status=400)

        messages.error(request, error_message)
        return redirect("reservations:list")

    success_message = "رزرو با موفقیت آرشیو شد."
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "success": True,
            "message": success_message
        })

    messages.success(request, success_message)
    return redirect("reservations:list")


@login_required
@require_POST
def reservation_cancel(request, pk):

    if not can_delete_reservation(request.user):
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    if reservation.status in [
        ReservationStatus.DELIVERED,
        ReservationStatus.RETURNED,
        ReservationStatus.LAUNDRY,
        ReservationStatus.READY,
        ReservationStatus.CANCELLED,
        ReservationStatus.ARCHIVED,
    ]:
        return HttpResponseForbidden()

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
def reservation_restore(request, pk):

    if not request.user.is_superuser:
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    try:
        ReservationStatusService.restore(reservation, request.user)
    except (ValidationError, PermissionDenied) as exc:
        error_message = str(exc) or "بازگردانی رزرو امکان‌پذیر نیست."
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({
                "success": False,
                "message": error_message
            }, status=400)

        messages.error(request, error_message)
        return redirect("reservations:archive")

    success_message = "رزرو با موفقیت بازگردانی شد."
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "success": True,
            "message": success_message
        })

    messages.success(request, success_message)
    return redirect("reservations:archive")


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
            "event_date": date_to_iso(event_date)
        })

    return JsonResponse({
        "success": True,
        "available": False,
        "message": "این لباس در این بازه زمانی رزرو شده است."
    })
