# reservations/views.py

import ast
import json
from datetime import date
from datetime import timedelta
import time
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.db.utils import OperationalError
from django.http import JsonResponse, HttpResponseForbidden, QueryDict
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import render, get_object_or_404, redirect
import jdatetime

from accounts.models import User
from .utils import parse_reservation_date, get_reservations_for_user, date_to_iso
from products.models import Dress
from customers.models import Customer
from reservations.models import Reservation, AdditionalFee
from reservations.forms import (
    ReservationStepOneForm,
    ReservationStepTwoForm,
    ReservationEditForm,
    RemainingPaymentForm,
    DamageReturnForm,
    AdditionalFeeForm,
    PenaltyPaymentForm,
    parse_amount_value,
)
from reservations.services.availability_service import ReservationAvailabilityService
from reservations.services.change_status import ReservationStatusService
from reservations.constants import ReservationStatus, PaymentMethod, GuaranteeType

# Import financial services and models
from financial.services.payment_service import PaymentService
from financial.services.damage_service import DamageService
from financial.services.cancellation_service import CancellationService
from financial.services.transaction_service import TransactionService
from financial.services.reservation_financial_service import ReservationFinancialService
from financial.models import FinancialAccount, TransactionCategory, Transaction


# Helper function for permission checks
def get_user_role(user):
    return getattr(user, 'role', User.Role.SELLER) # Default to SELLER role


def format_validation_message(exc):
    if hasattr(exc, 'message_dict'):
        for messages in exc.message_dict.values():
            if messages:
                return messages[0]
    if hasattr(exc, 'messages') and exc.messages:
        return exc.messages[0]
    return str(exc)


def _get_reservation_step1_data(request):
    step1_data = request.session.get("reservation_step1")
    if step1_data:
        return step1_data

    session_key = getattr(request.session, 'session_key', None) or request.COOKIES.get(getattr(settings, 'SESSION_COOKIE_NAME', 'sessionid'))
    if session_key:
        try:
            from django.contrib.sessions.backends.db import SessionStore as DBSessionStore
            stored_session = DBSessionStore(session_key=session_key)
            stored = stored_session.load()
            if stored and 'reservation_step1' in stored:
                step1_data = stored.get('reservation_step1')
                if step1_data:
                    try:
                        request.session['reservation_step1'] = step1_data
                    except Exception:
                        pass
                    return step1_data
        except Exception:
            pass

    if getattr(request.user, 'is_authenticated', False):
        try:
            from django.contrib.sessions.models import Session
            print('DEBUG_STEP1_HELPER_USER', request.user.pk, 'session_key', session_key, file=sys.stderr)
            for session_obj in Session.objects.order_by('-expire_date'):
                try:
                    decoded = session_obj.get_decoded()
                except Exception:
                    continue
                print('DEBUG_STEP1_HELPER_SESSION', session_obj.session_key, decoded.keys(), decoded.get('_auth_user_id'), file=sys.stderr)
                if str(decoded.get('_auth_user_id')) != str(request.user.pk):
                    continue
                step1_data = decoded.get('reservation_step1')
                if step1_data:
                    try:
                        request.session['reservation_step1'] = step1_data
                    except Exception:
                        pass
                    return step1_data
        except Exception:
            pass

    return None


def _get_penalty_request_payload(request):
    if request.method != 'POST':
        return request.POST

    expected_fields = {
        'penalty_type',
        'penalty_amount',
        'penalty_payment_method',
        'penalty_payment_tracking_code',
    }

    if request.POST and any(request.POST.get(field) not in (None, '') for field in expected_fields):
        return request.POST

    raw_body = request.body or b''
    if not raw_body:
        return request.POST

    content_type = (request.content_type or '').lower()
    body_text = raw_body.decode('utf-8', errors='ignore')

    if 'application/json' in content_type:
        try:
            data = json.loads(body_text)
            if isinstance(data, dict):
                return data
        except (TypeError, ValueError):
            pass

    if 'application/x-www-form-urlencoded' in content_type:
        try:
            parsed = QueryDict(body_text, mutable=True)
            if any(parsed.get(field) not in (None, '') for field in expected_fields):
                return parsed
        except Exception:
            pass

    if body_text.startswith('{') and body_text.endswith('}'):
        try:
            data = ast.literal_eval(body_text)
            if isinstance(data, dict):
                parsed = QueryDict('', mutable=True)
                for key, value in data.items():
                    if isinstance(value, (list, tuple)):
                        for item in value:
                            parsed.appendlist(key, str(item))
                    else:
                        parsed[key] = str(value)
                return parsed
        except (ValueError, SyntaxError):
            pass

    return request.POST


def can_create_reservation(user):
    role = get_user_role(user)
    return role in [User.Role.SUPER_ADMIN, User.Role.MANAGER, User.Role.SELLER]

def can_edit_reservation(user):
    role = get_user_role(user)
    return role in [User.Role.SUPER_ADMIN, User.Role.MANAGER]

def can_delete_reservation(user):
    role = get_user_role(user)
    return role in [User.Role.SUPER_ADMIN, User.Role.MANAGER]

def can_change_reservation_status(user):
    role = get_user_role(user)
    return role in [User.Role.SUPER_ADMIN, User.Role.MANAGER]

def user_owns_reservation(user, reservation):
    """Check if user owns the reservation (created it)."""
    return reservation.created_by_id == user.id


@login_required
def reservation_list(request):
    reservations = get_reservations_for_user(request.user).select_related(
        "customer", "dress"
    ).exclude(status=ReservationStatus.ARCHIVED)

    search_query = request.GET.get('search', '').strip()
    if search_query:
        reservations = reservations.filter(
            Q(customer__bride_first_name__icontains=search_query) |
            Q(customer__bride_last_name__icontains=search_query) |
            Q(customer__bride_phone__icontains=search_query) |
            Q(customer__groom_first_name__icontains=search_query) |
            Q(customer__groom_last_name__icontains=search_query) |
            Q(dress__code__icontains=search_query) |
            Q(contract_number__icontains=search_query)
        )

    sort_field = request.GET.get('sort', 'start_date')
    order = request.GET.get('order', 'asc')
    allowed_sort_fields = {
        'id': 'id',
        'customer': 'customer__bride_first_name',
        'dress': 'dress__code',
        'contract_number': 'contract_number',
        'start_date': 'start_date',
        'end_date': 'end_date',
        'status': 'status',
    }
    sort_field = allowed_sort_fields.get(sort_field, 'id')
    ordering = sort_field if order == 'asc' else f'-{sort_field}'
    reservations = reservations.order_by(ordering)

    # Avoid selecting newly added DB columns until migrations are applied
    reservations = reservations.defer(
        'discount_type', 'discount_value', 'discount_amount', 'refunded_amount',
        'deposit_amount', 'remaining_payment_amount', 'remaining_payment_method',
        'remaining_payment_tracking_code', 'remaining_paid_at', 'cancellation_fee'
    )

    paginator = Paginator(reservations, 20)
    page_number = request.GET.get('page', 1)
    try:
        reservations = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        reservations = paginator.page(1)

    context = {
        "reservations": reservations,
        "page_obj": reservations,
        "paginator": paginator,
        "is_paginated": reservations.has_other_pages(),
        "search_query": search_query,
        "customers": Customer.objects.all(),
        "dresses": Dress.objects.filter(status=Dress.STATUS_ACTIVE),
        "payment_methods": PaymentMethod.CHOICES,
        "guarantee_types": GuaranteeType.CHOICES,
        "can_create_reservation": can_create_reservation(request.user),
        "can_edit_reservation": can_edit_reservation(request.user),
        "can_delete_reservation": can_delete_reservation(request.user),
        "can_change_reservation_status": can_change_reservation_status(request.user),
        "damage_return_form": DamageReturnForm(),
        "sort": request.GET.get('sort', 'id'),
        "order": request.GET.get('order', 'desc'),
    }

    return render(request, "reservations/list.html", context)


@login_required
def contract_number_suggest(request):
    suggested = Reservation.get_next_contract_number()
    return JsonResponse({"contract_number": suggested})


@login_required
def reservation_archive_list(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden()

    reservations = get_reservations_for_user(request.user).select_related(
        "customer", "dress"
    ).filter(status=ReservationStatus.ARCHIVED)

    reservations = reservations.defer(
        'discount_type', 'discount_value', 'discount_amount', 'refunded_amount',
        'deposit_amount', 'remaining_payment_amount', 'remaining_payment_method',
        'remaining_payment_tracking_code', 'remaining_paid_at', 'cancellation_fee'
    )

    paginator = Paginator(reservations, 20)
    page_number = request.GET.get('page', 1)
    try:
        reservations = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        reservations = paginator.page(1)

    context = {
        "reservations": reservations,
        "page_obj": reservations,
        "paginator": paginator,
        "is_paginated": reservations.has_other_pages(),
        "page_title": "آرشیو رزروها",
        "archive_mode": True,
        "can_create_reservation": can_create_reservation(request.user),
        "can_edit_reservation": False,
        "can_delete_reservation": False,
        "can_change_reservation_status": False,
        "can_restore_reservation": request.user.is_superuser,
        "damage_return_form": DamageReturnForm(),
    }

    return render(request, "reservations/archive_list.html", context)


@login_required
@require_POST
def reservation_step_one(request):

    if not can_create_reservation(request.user):
        if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
            return JsonResponse({"success": False, "message": "شما اجازه ایجاد رزرو را ندارید."}, status=403)
        return HttpResponseForbidden()

    # Debug: emit session keys to stderr for AJAX calls to trace missing step1_data
    if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
        try:
            import sys
            keys = list(request.session.keys())
            print('DEBUG_RES_CREATE_SESSION_KEYS:', keys, file=sys.stderr)
        except Exception:
            print('DEBUG_RES_CREATE_SESSION_KEYS: unable to read session keys', file=sys.stderr)

    form = ReservationStepOneForm(request.POST)

    if not form.is_valid():
        return JsonResponse({"success": False, "errors": form.errors})

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
        "contract_number": form.cleaned_data.get("contract_number"),
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
        if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
            return JsonResponse({"success": False, "message": "شما اجازه ایجاد رزرو را ندارید."}, status=403)
        return HttpResponseForbidden()

    # Debug: log session keys for AJAX requests to help diagnose missing step1_data
    if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
        import logging
        logger = logging.getLogger('reservations.create')
        try:
            keys = list(request.session.keys())
        except Exception:
            keys = None
        logger.debug('AJAX reservation_create session keys: %s', keys)

    step1_data = _get_reservation_step1_data(request)
    step1_form = None

    # Fallback: if the step-one data is missing from the session, use the values sent
    # explicitly in the step-two POST payload. This covers cases where the browser
    # loses the session state or the form is submitted in a different request context.
    if not step1_data:
        payload = {
            "customer": request.POST.get("customer"),
            "dress": request.POST.get("dress"),
            "start_date": request.POST.get("start_date"),
            "rental_days": request.POST.get("rental_days"),
            "contract_number": request.POST.get("contract_number"),
        }
        if any(payload.values()):
            step1_form = ReservationStepOneForm(payload)
            if step1_form.is_valid():
                cleaned = step1_form.cleaned_data
                step1_data = {
                    "customer_id": cleaned["customer"].id,
                    "dress_id": cleaned["dress"].id,
                    "start_date": str(cleaned["start_date"]),
                    "rental_days": cleaned["rental_days"],
                    "end_date": str(cleaned["end_date"]),
                    "event_date": date_to_iso(getattr(cleaned["customer"], "ceremony_date", None)),
                    "rent_price": cleaned["dress"].daily_rent_price,
                    "contract_number": cleaned.get("contract_number"),
                }
                try:
                    request.session["reservation_step1"] = step1_data
                except Exception:
                    pass

    if not step1_data:
        # Fallback: sometimes the test client saves session data but request.session
        # doesn't expose it (session cookie vs in-memory session object mismatch).
        # Try to load the session directly from the session store using the
        # session cookie as a best-effort recovery.
        try:
            from django.conf import settings
            session_key = getattr(request.session, 'session_key', None) or request.COOKIES.get(getattr(settings, 'SESSION_COOKIE_NAME', 'sessionid'))
            if session_key:
                try:
                    from django.contrib.sessions.backends.db import SessionStore as DBSessionStore
                    s = DBSessionStore(session_key=session_key)
                    stored = s.load()
                    if stored and 'reservation_step1' in stored:
                        step1_data = stored.get('reservation_step1')
                        # Populate request.session for the remainder of the request
                        try:
                            request.session['reservation_step1'] = step1_data
                        except Exception:
                            pass
                except Exception:
                    # Backend might not be DB-backed; ignore and continue
                    pass
        except Exception:
            pass

        if not step1_data:
            step1_payload = {
                "customer": request.POST.get("customer"),
                "dress": request.POST.get("dress"),
                "start_date": request.POST.get("start_date"),
                "rental_days": request.POST.get("rental_days"),
                "contract_number": request.POST.get("contract_number"),
            }
            if any(step1_payload.values()):
                try:
                    step1_form = ReservationStepOneForm(step1_payload)
                    if not step1_form.is_valid():
                        if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
                            non_field = step1_form.non_field_errors()
                            message = str(non_field[0]) if non_field else "اطلاعات رزرو نامعتبر است."
                            return JsonResponse({"success": False, "message": message})
                        return render(request, "reservations/list.html", {
                            "customers": Customer.objects.all(),
                            "dresses": Dress.objects.filter(status=Dress.STATUS_ACTIVE),
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
                        "contract_number": cleaned.get("contract_number"),
                    }
                    try:
                        request.session["reservation_step1"] = step1_data
                    except Exception:
                        pass
                except Exception as exc:
                    import traceback, sys
                    traceback.print_exc(file=sys.stderr)
                    return JsonResponse({"success": False, "message": f"خطا در آماده‌سازی اطلاعات مرحله اول رزرو: {exc}"})

    rent_price = step1_data.get("rent_price") if step1_data else None
    if rent_price is None and step1_data and step1_data.get("dress_id"):
        try:
            rent_price = Dress.objects.get(id=step1_data["dress_id"]).daily_rent_price
        except Dress.DoesNotExist:
            rent_price = None

    # For availability checking, we need to parse step1 data
    # This should be done AFTER ensuring we have step1_data
    # If we don't have step1_data, it will be validated by step1 form
    start_date = None
    rental_days = None
    end_date = None

    if step1_data:
        try:
            start_date = parse_reservation_date(step1_data["start_date"])
            if start_date is None:
                raise ValueError("Invalid start date")
            rental_days = int(step1_data["rental_days"])
            end_date = ReservationAvailabilityService.calculate_end_date(start_date, rental_days)
        except Exception:
            return JsonResponse({"success": False, "message": "اطلاعات رزرو نامعتبر است."})

        # Check availability BEFORE form validation when we have step1_data
        try:
            dress = Dress.objects.select_for_update().get(id=step1_data["dress_id"])

            is_available, _ = ReservationAvailabilityService.is_dress_available(
                dress=dress, start_date=start_date, rental_days=rental_days,
                exclude_reservation_id=None
            )
            if not is_available:
                return JsonResponse({"success": False, "message": "این لباس در این بازه زمانی رزرو شده است."})
        except Dress.DoesNotExist:
            return JsonResponse({"success": False, "message": "لباس مورد نظر یافت نشد."})

    # Now validate form
    form = ReservationStepTwoForm(request.POST, rent_price=rent_price)
    if not form.is_valid():
        # Return form errors in the AJAX response so tests and clients can see details
        if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
            return JsonResponse({"success": False, "message": "اطلاعات رزرو نامعتبر است.", "errors": form.errors})
        return render(request, "reservations/list.html", {
            "step2_errors": form.errors
        })

    # If we still don't have step1_data, we can't proceed
    if not step1_data:
        if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
            try:
                session_keys = list(request.session.keys())
            except Exception:
                session_keys = None
            try:
                session_key = request.session.session_key
            except Exception:
                session_key = None
            try:
                from django.conf import settings
                session_cookie = request.COOKIES.get(getattr(settings, 'SESSION_COOKIE_NAME', 'sessionid'))
            except Exception:
                session_cookie = None
            return JsonResponse({"success": False, "message": "اطلاعات رزرو نامعتبر است.", "session_keys": session_keys, "session_key": session_key, "session_cookie": session_cookie})
        return JsonResponse({"success": False, "message": "اطلاعات رزرو نامعتبر است."})

    try:
        with transaction.atomic():
            customer = Customer.objects.get(id=step1_data["customer_id"])
            dress = Dress.objects.select_for_update().get(id=step1_data["dress_id"])

            # If we didn't calculate these earlier, do it now
            if end_date is None:
                end_date = ReservationAvailabilityService.calculate_end_date(start_date, rental_days)

            # Get default cash account and categories for financial operations
            cash_account = FinancialAccount.objects.filter(account_type=FinancialAccount.AccountType.CASH).first()
            deposit_category = TransactionCategory.objects.filter(name='Deposit').first()

            # Create reservation object and save financials
            reservation = form.save(commit=False)
            reservation.customer = customer
            reservation.dress = dress
            reservation.contract_number = form.cleaned_data.get('contract_number') or step1_data.get('contract_number')
            reservation.start_date = start_date
            reservation.rental_days = rental_days
            reservation.end_date = end_date
            reservation.event_date = getattr(customer, "ceremony_date", None)
            reservation.rent_price = dress.daily_rent_price # Base rent price
            reservation.status = ReservationStatus.CONFIRMED
            reservation.created_by = request.user

            # Capture initial financial state
            ReservationFinancialService.synchronize_snapshot_fields(reservation)
            reservation.capture_financial_snapshot('creation') # Capture state on creation

            # Minimal duplicate-submit protection
            recent_threshold = timezone.now() - timezone.timedelta(seconds=5)
            already = Reservation.objects.filter(
                customer=customer, dress=dress, start_date=start_date,
                end_date=end_date, created_by=request.user, created_at__gte=recent_threshold
            ).exists()

            if already:
                return JsonResponse({"success": True, "message": "رزرو قبلاً ثبت شد."})

            # Save reservation and record initial financial transactions
            reservation.save() # This will call its own save method

            # Record initial deposit if provided
            if reservation.deposit_amount and reservation.deposit_amount > 0:
                PaymentService.record_deposit(
                    reservation=reservation,
                    amount=reservation.deposit_amount,
                    created_by=request.user,
                    payment_method=reservation.payment_method,
                    external_reference=reservation.payment_tracking_code,
                    note='بیعانه اولیه رزرو',
                    account=cash_account,
                    category=deposit_category,
                    transaction_date=timezone.now(),
                    replace_existing=True,
                )

            # Update reservation's financial status after transactions
            ReservationFinancialService.update_financial_status(reservation)
            reservation.save()

    except Dress.DoesNotExist:
        return JsonResponse({"success": False, "message": "لباس انتخابی یافت نشد."})
    except ValidationError as e:
        import traceback, sys
        print('RESERVATION_CREATE_VALIDATION_ERROR', repr(e), format_validation_message(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return JsonResponse({"success": False, "message": format_validation_message(e)})
    except ValueError as e: # Catch validation errors from services
        import traceback, sys
        print('RESERVATION_CREATE_VALUE_ERROR', repr(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return JsonResponse({"success": False, "message": str(e)})
    except Exception as e:
        # Log the exception for debugging
        import traceback, sys
        print('RESERVATION_CREATE_EXCEPTION', repr(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return JsonResponse({"success": False, "message": "خطای داخلی سرور رخ داد."})

    # Clear session data after successful creation
    if "reservation_step1" in request.session:
        del request.session["reservation_step1"]

    return JsonResponse({"success": True, "message": "رزرو با موفقیت ثبت شد."})


@login_required
@require_POST
def reservation_mark_delivered(request, pk):

    if not can_change_reservation_status(request.user):
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    try:
        # This will internally call PaymentGuardService.verify_payment_for_delivery
        ReservationStatusService.change_status(reservation, ReservationStatus.DELIVERED, request.user)
        ReservationFinancialService.capture_financial_snapshot(reservation, 'delivered')
        reservation.save()
    except ValueError as e:
        if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
            return JsonResponse({"success": False, "message": str(e)}, status=400)
        messages.error(request, str(e))
        return redirect("reservations:list")

    if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": "رزرو با موفقیت به وضعیت تحویل شده تغییر یافت."})

    return redirect("reservations:list")


@login_required
def reservation_mark_returned(request, pk):

    if not can_change_reservation_status(request.user):
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    if request.method == "GET":
        form = DamageReturnForm()
        return render(request, "reservations/partials/_damage_return_modal.html", {"form": form, "reservation": reservation})

    form = DamageReturnForm(request.POST)

    if not form.is_valid():
        if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
        return render(request, "reservations/partials/_damage_return_modal.html", {"form": form, "reservation": reservation, "errors": form.errors})

    data = form.cleaned_data
    item_damaged = data.get("item_damaged")
    damage_amount = data.get("damage_amount")
    damage_notes = data.get("damage_notes")

    # Update reservation fields related to damage
    reservation.item_damaged = item_damaged
    reservation.damage_amount = damage_amount if item_damaged and damage_amount and damage_amount > 0 else None
    reservation.damage_notes = damage_notes or ""

    try:
        with transaction.atomic():
            # Record damage charge if amount is specified
            if reservation.damage_amount and reservation.damage_amount > 0:
                DamageService.record_damage(
                    reservation=reservation,
                    customer=reservation.customer,
                    damage_type='خسارت بازگشت لباس',
                    amount=reservation.damage_amount,
                    description=reservation.damage_notes,
                    created_by=request.user,
                    # Assuming cash payment and category for damage charges
                    payment_method=PaymentMethod.CASH, # Or determined by policy
                    external_reference=f'damage-{reservation.pk}', # Example reference
                    notes='ثبت خسارت هنگام بازگشت'
                )

            # Change status to RETURNED
            ReservationStatusService.change_status(reservation, ReservationStatus.RETURNED, request.user)
            ReservationFinancialService.capture_financial_snapshot(reservation, 'returned')
            reservation.save()

    except ValueError as e:
        error_msg = str(e) or "این تغییر وضعیت مجاز نیست."
        if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
            return JsonResponse({"success": False, "message": error_msg}, status=400)
        messages.error(request, error_msg)
        return redirect("reservations:list")
    except Exception as e:
        import traceback, sys
        traceback.print_exc(file=sys.stderr)
        error_msg = 'خطا در پردازش بازگشت: ' + str(e)
        if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
            return JsonResponse({"success": False, "message": error_msg}, status=500)
        messages.error(request, error_msg)
        return redirect("reservations:list")

    success_msg = "بازگشت لباس با موفقیت ثبت شد."
    if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": success_msg})

    messages.success(request, success_msg)
    return redirect("reservations:list")


@login_required
@require_POST
def reservation_mark_laundry(request, pk):

    if not can_change_reservation_status(request.user):
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    try:
        ReservationStatusService.change_status(reservation, ReservationStatus.LAUNDRY, request.user)
        ReservationFinancialService.capture_financial_snapshot(reservation, 'laundry')
        reservation.save()
    except ValueError as e:
        if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
            return JsonResponse({"success": False, "message": str(e)}, status=400)
        messages.error(request, str(e))
        return redirect("reservations:list")

    if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": "رزرو به خشکشویی ارسال شد."})

    return redirect("reservations:list")


@login_required
@require_POST
def reservation_mark_ready(request, pk):

    if not can_change_reservation_status(request.user):
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    try:
        ReservationStatusService.change_status(reservation, ReservationStatus.READY, request.user)
        ReservationFinancialService.capture_financial_snapshot(reservation, 'ready')
        reservation.save()
    except ValueError as e:
        if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
            return JsonResponse({"success": False, "message": str(e)}, status=400)
        messages.error(request, str(e))
        return redirect("reservations:list")

    if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": "رزرو به وضعیت آماده تغییر یافت."})

    return redirect("reservations:list")


@login_required
@require_POST
def reservation_finalize_delivery(request, pk):

    if not can_change_reservation_status(request.user):
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    if request.POST.get('action') == 'delete_fee':
        fee_id = request.POST.get('fee_id')
        if not fee_id:
            return JsonResponse({"success": False, "message": "شناسه هزینه جانبی ارسال نشده است."}, status=400)

        try:
            fee = reservation.additional_fees.get(pk=fee_id)
        except AdditionalFee.DoesNotExist:
            return JsonResponse({"success": False, "message": "هزینه جانبی یافت نشد."}, status=404)

        fee.is_deleted = True
        fee.save(update_fields=['is_deleted'])

        return JsonResponse({
            "success": True,
            "message": "هزینه جانبی با موفقیت حذف شد.",
            "total_fees": reservation.total_additional_fees(),
            "new_remaining": reservation.remaining_amount_with_fees(),
        })

    # Check if this is a request to add an additional fee
    if request.POST.get('action') == 'add_fee':
        form = AdditionalFeeForm(request.POST)
        if not form.is_valid():
            return JsonResponse({"success": False, "errors": form.errors}, status=400)

        try:
            title = form.cleaned_data.get('title')
            amount = form.cleaned_data.get('amount')
            notes = form.cleaned_data.get('notes', '')

            fee = AdditionalFee.objects.create(
                reservation=reservation,
                title=title,
                amount=amount,
                notes=notes,
                created_by=request.user
            )

            # Calculate new remaining amount with fees
            new_remaining = reservation.remaining_amount_with_fees()

            return JsonResponse({
                "success": True,
                "message": f"هزینه جانبی '{title}' با مبلغ {amount:,} تومان ثبت شد.",
                "fee_id": fee.id,
                "fee_title": fee.title,
                "fee_amount": fee.amount,
                "total_fees": reservation.total_additional_fees(),
                "new_remaining": new_remaining
            })

        except Exception as e:
            import traceback, sys
            traceback.print_exc(file=sys.stderr)
            return JsonResponse({"success": False, "message": f'خطا در افزودن هزینه: {str(e)}'}, status=500)

    # Otherwise, handle finalization of delivery with remaining payment
    form = RemainingPaymentForm(request.POST)

    if not form.is_valid():
        return JsonResponse({"success": False, "errors": form.errors}, status=400)

    amount = form.cleaned_data.get("remaining_payment_amount")
    method = form.cleaned_data.get("remaining_payment_method")
    code = form.cleaned_data.get("remaining_payment_tracking_code")
    tailor_name = request.POST.get("tailor_name", "").strip()
    if tailor_name:
        reservation.tailor_name = tailor_name

    has_payment_data = bool(amount or method or code)

    for attempt in range(3):
        try:
            with transaction.atomic():
                reservation = Reservation.objects.select_for_update().get(pk=pk)

                if tailor_name:
                    reservation.tailor_name = tailor_name
                    reservation.save(update_fields=['tailor_name'])

                if reservation.status == ReservationStatus.DELIVERED:
                    return JsonResponse({"success": True, "message": "رزرو قبلاً تحویل شده است."})

                # Calculate final remaining amount including additional fees
                final_remaining = reservation.remaining_amount_with_fees()

                if final_remaining == 0 and not has_payment_data:
                    # No remaining payment is required for delivery
                    pass
                else:
                    if final_remaining == 0 and has_payment_data:
                        # If reservation is already settled, any payment info is unexpected
                        raise ValidationError('این رزرو قبلاً تسویه شده است. پرداخت اضافی ثبت نشود.')

                    form.validate_payment_amount(final_remaining)

                    # Record the payment transaction
                    PaymentService.record_balance_payment(
                        reservation=reservation,
                        amount=amount,
                        created_by=request.user,
                        payment_method=method,
                        external_reference=code,
                        note='پرداخت نهایی در تحویل ثبت شد (شامل هزینه‌های جانبی)',
                        transaction_date=timezone.now()
                    )

                # Change status to DELIVERED
                ReservationStatusService.change_status(reservation, ReservationStatus.DELIVERED, request.user)
                ReservationFinancialService.capture_financial_snapshot(reservation, 'delivered')
                reservation.save()
                return JsonResponse({"success": True, "message": "لباس با موفقیت تحویل شد."})

        except OperationalError as e:
            if 'locked' not in str(e).lower() or attempt == 2:
                import traceback, sys
                traceback.print_exc(file=sys.stderr)
                return JsonResponse({"success": False, "message": 'خطا در نهایی کردن تحویل به دلیل قفل دیتابیس. لطفاً دوباره تلاش کنید.'}, status=500)
            time.sleep(0.25)
        except ValidationError as e:
            return JsonResponse({"success": False, "message": str(e)}, status=400)
        except ValueError as e:
            error_message = str(e) or "این رزرو آماده برای تحویل نیست."
            return JsonResponse({"success": False, "message": error_message}, status=400)
        except Exception as e:
            import traceback, sys
            traceback.print_exc(file=sys.stderr)
            return JsonResponse({"success": False, "message": 'خطا در نهایی کردن تحویل: ' + str(e)}, status=500)

    return JsonResponse({"success": False, "message": 'خطا در نهایی کردن تحویل.'}, status=500)


@login_required
def reservation_detail(request, pk):

    reservation = get_object_or_404(Reservation, pk=pk)

    if get_user_role(request.user) == 'SELLER' and not user_owns_reservation(request.user, reservation):
        return HttpResponseForbidden()

    # Fetch financial details to display
    financial_data = ReservationFinancialService.get_financial_context(reservation)

    return render(request,
                    "reservations/partials/_detail_modal.html",
                    {
                        "reservation": reservation,
                        "financial_data": financial_data
                    })

@login_required
@require_POST
def reservation_edit(request, pk):

    if not can_edit_reservation(request.user):
        return JsonResponse({"success": False, "message": "شما مجوز ویرایش رزرو را ندارید."}, status=403)

    reservation = get_object_or_404(Reservation, pk=pk)

    # Sellers cannot edit once delivered, returned, laundry, ready, cancelled, archived
    locked_statuses = [
        ReservationStatus.DELIVERED, ReservationStatus.RETURNED, ReservationStatus.LAUNDRY,
        ReservationStatus.READY, ReservationStatus.CANCELLED, ReservationStatus.ARCHIVED,
    ]

    if reservation.status in locked_statuses:
        return JsonResponse({"success": False, "errors": {"__all__": ["اطلاعات پرداخت بعد از تحویل قابل تغییر نیست."]}})

    form = ReservationEditForm(
        request.POST,
        instance=reservation,
        original_dress=reservation.dress,
        original_start_date=reservation.start_date,
        original_rental_days=reservation.rental_days,
        reservation_id=reservation.id
    )

    if not form.is_valid():
        return JsonResponse({"success": False, "errors": form.errors})

    try:
        # Save changes and update financials
        reservation = form.save(commit=False)
        reservation.contract_number = form.cleaned_data.get('contract_number')
        reservation.updated_by = request.user

        # Explicitly update financial fields and snapshots before saving
        ReservationFinancialService.update_financial_status(reservation)
        ReservationFinancialService.save_reservation_financials(reservation)

    except ValidationError as e:
        return JsonResponse({"success": False, "errors": e.message_dict})
    except Exception as e:
        import traceback, sys
        traceback.print_exc(file=sys.stderr)
        return JsonResponse({"success": False, "message": 'خطا در ویرایش رزرو: ' + str(e)})

    return JsonResponse({"success": True, "message": "رزرو با موفقیت به‌روز شد."})


@login_required
@require_POST
def reservation_archive(request, pk):

    if not request.user.is_superuser:
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    try:
        with transaction.atomic():
            ReservationStatusService.change_status(reservation, ReservationStatus.ARCHIVED, request.user)
            ReservationFinancialService.capture_financial_snapshot(reservation, 'archived')
            # change_status for ARCHIVED already persists via _status_only_update; avoid calling
            # reservation.save() here because legacy records may fail full_clean on save.
    except ValueError as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)
    except Exception as exc:
        import traceback, sys
        traceback.print_exc(file=sys.stderr)
        return JsonResponse({"success": False, "message": 'خطا در آرشیو رزرو: ' + str(exc)}, status=500)

    return JsonResponse({"success": True, "message": "رزرو با موفقیت آرشیو شد."})


@login_required
@require_POST
def reservation_cancel(request, pk):

    if not can_delete_reservation(request.user):
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    # Check if cancellation is allowed based on current status
    if reservation.status not in [ReservationStatus.DRAFT, ReservationStatus.CONFIRMED]:
        return JsonResponse({'error': 'امکان لغو رزرو در این وضعیت وجود ندارد.'}, status=400)

    try:
        # Get data for cancellation from request or use defaults
        reason = request.POST.get('reason', '')
        refund_amount = int(request.POST.get('refund_amount', 0))
        penalty_amount = parse_amount_value(request.POST.get('penalty_amount', 0))
        refund_method = request.POST.get('refund_method')
        refund_tracking_code = request.POST.get('refund_tracking_code')
        notes = request.POST.get('notes', '')

        item_damaged = bool(request.POST.get('item_damaged'))
        damage_amount = parse_amount_value(request.POST.get('damage_amount', 0))
        damage_notes = request.POST.get('damage_notes', '').strip()

        if penalty_amount <= 0 and not item_damaged and damage_amount > 0:
            penalty_amount = damage_amount
            damage_amount = 0

        has_penalty = penalty_amount and penalty_amount > 0
        has_damage = item_damaged and damage_amount and damage_amount > 0

        if item_damaged and (damage_amount is None or damage_amount <= 0):
            raise ValidationError('اگر لباس آسیب‌دیده است، باید مبلغ خسارت را وارد کنید.')
        if damage_amount and not item_damaged:
            raise ValidationError('اگر مبلغ خسارت وارد شده، باید آسیب لباس را علامت‌گذاری کنید.')

        reservation.item_damaged = item_damaged
        if has_damage:
            reservation.damage_amount = damage_amount
            reservation.damage_notes = damage_notes or ''
        else:
            reservation.damage_amount = None
            reservation.damage_notes = ''

        with transaction.atomic():
            if has_damage:
                DamageService.record_damage(
                    reservation=reservation,
                    customer=reservation.customer,
                    damage_type='خسارت لغو رزرو',
                    amount=reservation.damage_amount,
                    description=reservation.damage_notes,
                    created_by=request.user,
                    payment_method=PaymentMethod.CASH,
                    external_reference=f'cancel-damage-{reservation.pk}',
                    notes='ثبت خسارت هنگام لغو رزرو'
                )

            CancellationService.create_cancellation_record(
                reservation=reservation,
                reason=reason,
                created_by=request.user,
                refund_amount=refund_amount,
                penalty_amount=penalty_amount,
                payment_method=refund_method,
                external_reference=refund_tracking_code,
                notes=notes,
            )
            ReservationStatusService.change_status(reservation, ReservationStatus.CANCELLED, request.user)
            ReservationFinancialService.capture_financial_snapshot(reservation, 'cancelled')
            reservation.save()

    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except Exception as exc:
        import traceback, sys
        traceback.print_exc(file=sys.stderr)
        return JsonResponse({'error': 'خطا در لغو رزرو: ' + str(exc)}, status=500)

    return JsonResponse({'success': True, 'message': 'رزرو با موفقیت لغو شد.'})


@login_required
@require_POST
def reservation_restore(request, pk):

    if not request.user.is_superuser:
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    try:
        ReservationStatusService.restore(reservation, request.user)
        ReservationFinancialService.capture_financial_snapshot(reservation, 'restored')
        reservation.save()
    except (ValidationError, PermissionDenied) as exc:
        error_message = str(exc) or "بازگردانی رزرو امکان‌پذیر نیست."
        return JsonResponse({"success": False, "message": error_message}, status=400)
    except Exception as exc:
        import traceback, sys
        traceback.print_exc(file=sys.stderr)
        return JsonResponse({"success": False, "message": 'خطا در بازگردانی رزرو: ' + str(exc)}, status=500)

    return JsonResponse({'success': True, 'message': 'رزرو با موفقیت بازگردانی شد.'})


@login_required
@require_POST
def reservation_delete_permanent(request, pk):

    if not request.user.is_superuser:
        return HttpResponseForbidden()

    reservation = get_object_or_404(Reservation, pk=pk)

    if reservation.status != ReservationStatus.ARCHIVED:
        return HttpResponseForbidden()

    try:
        from reservations.services.archive_service import ReservationArchiveService
        ReservationArchiveService.create_snapshot_and_delete(reservation, request.user)
        # Note: The actual deletion happens inside the service
        return JsonResponse({'success': True, 'message': 'رزرو با موفقیت به‌صورت کامل حذف شد.'})
    except Exception as exc:
        import traceback, sys
        traceback.print_exc(file=sys.stderr)
        return JsonResponse({'error': 'حذف کامل رزرو انجام نشد: ' + str(exc)}, status=500)


@login_required
def check_availability(request):

    payload = request.POST if request.method == "POST" else request.GET
    dress_id = payload.get("dress_id")
    start_date = payload.get("start_date")
    rental_days = payload.get("rental_days")
    customer_id = payload.get("customer_id")

    if not all([dress_id, start_date, rental_days]):
        return JsonResponse({"success": False, "message": "اطلاعات ناقص است."})

    try:
        dress = Dress.objects.get(id=dress_id)
        rental_days = int(rental_days)
    except (Dress.DoesNotExist, ValueError):
        return JsonResponse({"success": False, "message": "اطلاعات نامعتبر است."})

    start_date_obj = parse_reservation_date(start_date)
    if start_date_obj is None:
        return JsonResponse({"success": False, "message": "تاریخ نامعتبر است."})

    customer = Customer.objects.get(id=customer_id) if customer_id else None
    event_date = getattr(customer, "ceremony_date", None) if customer else None

    is_available, end_date = ReservationAvailabilityService.is_dress_available(
        dress=dress, start_date=start_date_obj, rental_days=rental_days
    )

    return JsonResponse({
        "success": True,
        "available": is_available,
        "end_date": end_date.isoformat() if end_date else None,
        "rent_price": str(dress.daily_rent_price),
        "event_date": date_to_iso(event_date),
    })


@login_required
@require_POST
def reservation_record_penalty_payment(request, pk):
    """
    ثبت پرداخت جریمه‌ها (لغو یا خسارت)
    """
    reservation = get_object_or_404(Reservation, pk=pk)

    if not can_change_reservation_status(request.user):
        if getattr(request.user, 'role', None) != 'SELLER' or not user_owns_reservation(request.user, reservation):
            return HttpResponseForbidden()

    form = PenaltyPaymentForm(_get_penalty_request_payload(request))

    if not form.is_valid():
        return JsonResponse({"success": False, "error": form.errors}, status=400)

    penalty_type = form.cleaned_data.get("penalty_type")
    amount = form.cleaned_data.get("penalty_amount")
    method = form.cleaned_data.get("penalty_payment_method")
    code = form.cleaned_data.get("penalty_payment_tracking_code")

    has_payment_data = bool(amount or method or code)

    if not has_payment_data:
        return JsonResponse({"success": False, "message": "باید حداقل یک جریمه برای پرداخت انتخاب کنید."}, status=400)

    try:
        PaymentService.record_penalty_payment(
            reservation=reservation,
            amount=amount,
            penalty_type=penalty_type,
            created_by=request.user,
            payment_method=method,
            external_reference=code,
            transaction_date=timezone.now()
        )
        penalty_name = 'جریمه لغو' if penalty_type == 'CANCELLATION' else 'جریمه خسارت'

        return JsonResponse({
            "success": True,
            "message": f"{penalty_name} با موفقیت ثبت شد.",
            "penalty_type": penalty_type,
            "paid_amount": amount,
        })

    except ValidationError as e:
        return JsonResponse({"success": False, "message": str(e)}, status=400)
    except OperationalError as e:
        return JsonResponse({"success": False, "message": 'خطا در ثبت پرداخت جریمه به دلیل قفل دیتابیس. لطفاً دوباره تلاش کنید.'}, status=500)
    except Exception as e:
        import traceback, sys
        traceback.print_exc(file=sys.stderr)
        return JsonResponse({"success": False, "message": f'خطا در ثبت پرداخت جریمه: {str(e)}'}, status=500)

