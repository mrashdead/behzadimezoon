from financial.models import Guarantee


class GuaranteeService:
    @staticmethod
    def create_guarantee(reservation, customer, tracking_code, guarantee_type, estimated_value=None, notes=None):
        return Guarantee.objects.create(
            reservation=reservation,
            customer=customer,
            tracking_code=tracking_code,
            guarantee_type=guarantee_type,
            estimated_value=estimated_value,
            notes=notes or ''
        )
