from financial.models import DamageRecord
from financial.services.transaction_service import TransactionService


class DamageService:
    @staticmethod
    def record_damage(reservation, customer, damage_type, amount=None, description=None, created_by=None):
        dr = DamageRecord.objects.create(
            reservation=reservation,
            customer=customer,
            damage_type=damage_type,
            amount=amount,
            description=description or '',
            collected=False
        )
        # optionally create a damage charge transaction if amount and created_by provided
        if amount and created_by:
            tx = TransactionService.create_damage_charge(
                reservation=reservation,
                amount=amount,
                created_by=created_by,
                note=f'خسارت برای رزرو #{reservation.pk}'
            )
            dr.related_transaction = tx
            dr.collected = True
            dr.payment_reference = tx.external_reference
            dr.save()
        return dr
