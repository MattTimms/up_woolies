from decimal import Decimal
from re import sub


def parse_money(money_str: str) -> Decimal:
    return Decimal(sub(r'[^\d.]', '', money_str))
