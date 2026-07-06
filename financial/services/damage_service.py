from django.core.exceptions import ValidationError
from django.db import transaction

from financial.models import DamageRecord
from financial.services.transaction_service import TransactionService
from financial.services.reservation_financial_service import ReservationFinancialService


class DamageService:
    @staticmethod
    def record_damage(reservation, customer, damage_type, amount=None, description=None, created_by=None, payment_method=None, external_reference=None):
        if amount is not None and amount < 0:
            raise ValidationError('مبلغ خسارت نمی‌تواند منفی باشد.')

        with transaction.atomic():
            dr = DamageRecord.objects.create(
                reservation=reservation,
                customer=customer,
                damage_type=damage_type,
                amount=amount,
                description=description or '',
                collected=False,
            )

            if amount and created_by:
                tx = TransactionService.create_damage_charge(
                    reservation=reservation,
                    amount=amount,
                    created_by=created_by,
                    payment_method=payment_method,
                    external_reference=external_reference,
                    note=f'خسارت رزرو #{reservation.pk}',
                )
                dr.related_transaction = tx
                dr.payment_reference = external_reference or tx.external_reference
                dr.collected = False
                dr.save()

            ReservationFinancialService.synchronize_snapshot_fields(reservation)
            reservation.save()
            return dr

    @staticmethod
    def record_damage_payment(damage_record, amount, created_by, payment_method=None, external_reference=None, note=None):
        if amount is None or amount < 0:
            raise ValidationError('مبلغ پرداخت خسارت باید عددی صفر یا مثبت باشد.')

        with transaction.atomic():
            tx = TransactionService.create_damage_payment(
                reservation=damage_record.reservation,
                amount=amount,
                created_by=created_by,
                payment_method=payment_method,
                external_reference=external_reference,
                note=note or f'پرداخت خسارت برای رزرو #{damage_record.reservation.pk}',
                related_transaction=damage_record.related_transaction,
            )
            damage_record.collected = True
            damage_record.payment_reference = external_reference or damage_record.payment_reference
            damage_record.related_transaction = tx
            damage_record.save()

            ReservationFinancialService.synchronize_snapshot_fields(damage_record.reservation)
            damage_record.reservation.save()
            return tx
