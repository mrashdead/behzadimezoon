# reservations/services/change_status.py

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from django.db import transaction
from reservations.services.state_machin import ReservationStateMachine
from reservations.services.payment_guards import PaymentGuardService
from reservations.services.availability_service import ReservationAvailabilityService
from reservations.constants import ReservationStatus


class ReservationStatusService:

    @staticmethod
    def change_status(reservation, new_status, user):
        old_status = reservation.status

        if not ReservationStateMachine.can_transition(
            reservation.status,
            new_status
        ):
            readable_status = dict(ReservationStatus.CHOICES).get(new_status, new_status)
            raise ValueError(
                f"انتقال وضعیت از {reservation.get_status_display()} به {readable_status} مجاز نیست."
            )

        if new_status == ReservationStatus.DELIVERED:
            PaymentGuardService.verify_payment_for_delivery(reservation)

        if new_status == ReservationStatus.RETURNED:
            reservation.returned_at = timezone.localdate()

        if new_status == ReservationStatus.CANCELLED:
            reservation.cancelled_at = timezone.now()

        if new_status == ReservationStatus.ARCHIVED:
            # Only archive when reservation is already finalized or canceled.
            reservation.previous_status = old_status
            reservation.archived_at = timezone.now()
            reservation.archived_by = user

        reservation.status = new_status
        reservation.updated_by = user
        reservation.save()

        # Create a status log entry for auditability.
        try:
            from reservations.models import ReservationStatusLog

            ReservationStatusLog.objects.create(
                reservation=reservation,
                old_status=old_status,
                new_status=new_status,
                changed_by=user
            )
        except Exception:
            # Logging must not break status change flow; swallow errors.
            pass

        return reservation

    @staticmethod
    def _infer_previous_status_from_logs(reservation):
        try:
            from reservations.models import ReservationStatusLog
        except ImportError:
            return None

        archived_log = reservation.status_logs.filter(
            new_status=ReservationStatus.ARCHIVED
        ).order_by('-changed_at').first()

        if archived_log and archived_log.old_status:
            return archived_log.old_status

        return None

    @staticmethod
    def validate_restore(reservation):
        if reservation.status != ReservationStatus.ARCHIVED:
            raise ValidationError("رزرو در وضعیت آرشیو نیست.")

        if not reservation.previous_status:
            inferred_status = ReservationStatusService._infer_previous_status_from_logs(reservation)
            if inferred_status:
                reservation.previous_status = inferred_status
                reservation.save(update_fields=['previous_status'])
            else:
                raise ValidationError("وضعیت قبلی رزرو نامشخص است.")

        final_states = {
            ReservationStatus.RETURNED,
            ReservationStatus.LAUNDRY,
            ReservationStatus.READY,
        }

        if reservation.previous_status in final_states:
            raise ValidationError("این رزرو قبلاً نهایی شده و امکان بازگردانی ندارد.")

        if reservation.previous_status in ReservationAvailabilityService.get_blocking_statuses():
            available, _ = ReservationAvailabilityService.is_dress_available(
                dress=reservation.dress,
                start_date=reservation.start_date,
                rental_days=reservation.rental_days,
                exclude_reservation_id=reservation.id
            )
            if not available:
                raise ValidationError("این محصول در بازه زمانی رزرو شده و امکان بازگردانی وجود ندارد.")

    @staticmethod
    def restore(reservation, user):
        if not getattr(user, 'is_superuser', False):
            raise PermissionDenied("دسترسی به این عملیات فقط برای سوپر‌یوزرها مجاز است.")

        ReservationStatusService.validate_restore(reservation)

        old_status = reservation.status
        reservation.status = reservation.previous_status
        reservation.previous_status = None
        reservation.archived_at = None
        reservation.archived_by = None
        reservation.updated_by = user

        with transaction.atomic():
            reservation.save()

            try:
                from reservations.models import ReservationStatusLog

                ReservationStatusLog.objects.create(
                    reservation=reservation,
                    old_status=old_status,
                    new_status=reservation.status,
                    changed_by=user
                )
            except Exception:
                pass

        return reservation
