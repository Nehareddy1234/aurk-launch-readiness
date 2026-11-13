from decimal import Decimal, ROUND_HALF_UP

ZERO = Decimal("0.00")

def money(value): return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def calculate_subtotal(items):
    return money(sum((money(i.variant.price_override if i.variant.price_override is not None else i.variant.product.current_price) * i.quantity for i in items), ZERO))

def calculate_total(subtotal, discount=ZERO, shipping=ZERO, tax=ZERO):
    return money(max(ZERO, subtotal - discount) + shipping + tax)
