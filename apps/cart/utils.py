from decimal import Decimal, ROUND_HALF_UP


def compute_line_total(unit_price, quantity):
    """
    Single canonical function for all line-price computation.
    Always uses ROUND_HALF_UP (never banker's rounding).
    Both cart rendering and order creation must call this — never multiply elsewhere.
    """
    return (Decimal(unit_price) * Decimal(quantity)).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
