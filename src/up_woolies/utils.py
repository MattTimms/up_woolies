from decimal import Decimal
from re import sub

from requests.adapters import HTTPAdapter
from requests import PreparedRequest, Response


def parse_money(money_str: str) -> Decimal:
    return Decimal(sub(r'[^\d.]', '', money_str))


class DefaultTimeoutAdapter(HTTPAdapter):
    def __init__(self, *args, timeout: float, **kwargs):
        self.timeout = timeout
        super().__init__(*args, **kwargs)

    def send(self, request: PreparedRequest, **kwargs) -> Response:
        kwargs['timeout'] = kwargs.get('timeout') or self.timeout
        return super().send(request, **kwargs)
