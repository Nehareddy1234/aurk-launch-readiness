from decimal import Decimal
from app.services.pricing import calculate_total, money

def test_money_rounds(): assert money("10.125") == Decimal("10.13")
def test_total_never_goes_negative(): assert calculate_total(Decimal("100"), Decimal("200")) == Decimal("0.00")
