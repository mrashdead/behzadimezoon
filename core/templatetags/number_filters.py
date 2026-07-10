from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def ir_currency(value):
    if value in (None, ""):
        return "0"

    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return str(value)

    if number == number.to_integral_value():
        return format(number.quantize(Decimal("1")), ",")

    return format(number.quantize(Decimal("0.01")), ",")
