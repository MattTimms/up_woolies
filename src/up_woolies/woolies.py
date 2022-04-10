import os
import re
import warnings
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Generator, Optional
from urllib.parse import urljoin

from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel, Extra, condecimal, PositiveInt
from rich.console import Console
from rich.prompt import Prompt

from utils import parse_money, new_session

# Get token from environment variables
load_dotenv(dotenv_path=find_dotenv())

# Define endpoint & headers
endpoint = "https://api.woolworthsrewards.com.au/wx/"
session = new_session()
session.headers.update({
    'client_id': '8h41mMOiDULmlLT28xKSv5ITpp3XBRvH',  # some universal client API ID key
    'User-Agent': 'up_woolies'  # some User-Agent
})


def __init():
    if (email := os.getenv('WOOLIES_EMAIL')) is not None and (password := os.getenv('WOOLIES_PASS')):
        auth = Auth.login(email, password)  # TODO implement token refresh
    elif (token := os.getenv('WOOLIES_TOKEN')) is not None:
        warnings.warn("WOOLIES_TOKEN is deprecated, use WOOLIES_[EMAIL|PASS] instead", DeprecationWarning)
        session.headers.update({'Authorization': f"Bearer {token}"})
        return
    else:
        auth = Auth.login_cli()  # TODO implement token refresh
    session.headers.update({'Authorization': f"Bearer {auth.bearer}"})


class Auth(BaseModel):
    bearer: str
    refresh: str
    bearerExpiredInSeconds: int
    refreshExpiredInSeconds: int
    passwordResetRequired: bool

    @classmethod
    def login(cls, email: str, password: str):
        url = urljoin(endpoint, 'v2/security/login/rewards')
        body = {'username': email, 'password': password}  # email/pass
        res = session.post(url=url, json=body)
        return cls.parse_obj(res.json()['data'])

    @classmethod
    def login_cli(cls):
        Console().print('Woolworths Login')
        email = Prompt.ask("Email")
        password = Prompt.ask("Password", password=True)
        return cls.login(email, password)  # TODO retry bad pass

    def refresh_token(self):
        url = urljoin(endpoint, 'v2/security/refreshLogin')
        body = {'refresh_token': self.refresh}
        res = session.post(url=url, json=body)

        _auth = self.parse_obj(res.json()['data'])
        for attr in self.__annotations__.keys():
            setattr(self, attr, getattr(_auth, attr))
        return self


# N.B. new login options are disabled as explain in changelog
# __init()
session.headers.update({'Authorization': f"Bearer {os.environ['WOOLIES_TOKEN']}"})


class PurchaseItem(BaseModel, extra=Extra.ignore):
    """ Dataclass of an unique purchased item """
    description: str
    amount: condecimal(gt=Decimal(0), decimal_places=2)
    quantity: Optional[PositiveInt] = 1
    weight: Optional[condecimal(gt=Decimal(0))]

    # TODO parse weight from description e.g. {'description': 'Abbotts Vil Bakery Country Grains 800g'}
    # TODO learn why certain items have leading symbols in description e.g. {'description': '#Cadbury Bar Twirl 39g'}
    # TODO what if I purchase two weighted goods separately in one transaction; I went back to the deli for more olives?


# Receipt-parsing regex patterns
PATTERN_MULTIPLE = re.compile(r'Qty (\d+) @ \$\d+\.\d+ each')  # e.g. 'Qty 2 @ $6.00 each'
PATTERN_WEIGHTED = re.compile(r'(\d+\.\d+) kg NET @ \$\d+\.\d+/kg')  # e.g. '0.716 kg NET @ $4.00/kg'
PATTERN_PRICE_REDUCED = re.compile(r'PRICE REDUCED BY \$\d+\.\d+(?: each|/kg)')  # e.g. PRICE REDUCED BY $3.15 each
PATTERN_CARD_PAYMENT = re.compile(r'X-\d{4}|EFT')  # e.g. X-1234 or EFT


class ReceiptDetails(BaseModel):
    """ Parsed-receipt items for a single transaction """
    # N.B. everything you see on a physical receipt is available from Woolies API
    items: List[PurchaseItem]
    value: Decimal  # value of items purchased
    amount_paid: Decimal  # Amount paid by card/cash (considering gift-cards &/or other discounts)

    class Config:
        fields = {'value': {'exclude': True}}

    @classmethod
    def from_raw(cls, response: Dict[str, Any]):
        """
        Returns class by parsing multi-line items from e-receipt response.
        Certain purchases express themselves across multiple lines in the receipt; i.e. purchases of duplicate items,
        or weighted goods. They are parsed to return self's items attribute where each purchased item may have

        :param response: data response from receipt endpoint; i.e. the return from get_receipt().
        """
        receipt_details_dict: Dict[str, Any] = {x['__typename']: x for x in response['receiptDetails']['details']}

        # Navigate down to the response's receipt detail items & payment summaries
        items: List[Dict[str, Any]] = receipt_details_dict['ReceiptDetailsItems']['items']  # Note: list is ordered
        total_value = parse_money(receipt_details_dict['ReceiptDetailsTotal']['total'])

        # Find payment amount (may differ from owed amount if discounts are applied)
        receipt_detail_payments = receipt_details_dict['ReceiptDetailsPayments']['payments']
        try:
            amount_paid = parse_money(next(filter(lambda payment: PATTERN_CARD_PAYMENT.match(payment['description']),
                                                  receipt_detail_payments))['amount'])
        except StopIteration:
            warnings.warn('unsupported payment method')
            amount_paid = total_value  # stopgap for cash-purchases or other edge-cases

        # Parse receipt items
        skip_to = 0
        purchases: List[PurchaseItem] = []
        for i, item in enumerate(items):
            if i < skip_to:
                continue

            # Handle multi-line receipt item
            if (amount := item['amount']) == '':
                skip_to = i + 2

                # Get next item
                try:
                    next_item = items[i + 1]
                except IndexError:
                    if PATTERN_PRICE_REDUCED.match(item['description']):
                        break  # Safe to ignore
                    raise ValueError("unforeseen edge case")

                # Handle purchase of multiple identical items
                if PATTERN_MULTIPLE.match(next_item_desc := next_item['description']):
                    quantity = PATTERN_MULTIPLE.findall(next_item_desc)[0]
                    purchase = PurchaseItem(description=item['description'],
                                            amount=next_item['amount'],
                                            quantity=quantity)

                    # Amend for any discounts for multiple identical items purchased
                    if i + 2 < len(items):
                        potential_discount_amount = items[i + 2]['amount']
                        if potential_discount_amount and (future_item_amount := Decimal(potential_discount_amount)) < 0:
                            purchase.amount += future_item_amount
                            skip_to += 1

                # Handle purchase of weighted item; e.g. fruit, veg, & deli
                elif PATTERN_WEIGHTED.match(next_item_desc):
                    weight = PATTERN_WEIGHTED.findall(next_item_desc)[0]
                    purchase = PurchaseItem(description=item['description'],
                                            amount=next_item['amount'],
                                            weight=weight,
                                            quantity=None)

                # Ignore "price reduced" message in receipt
                elif PATTERN_PRICE_REDUCED.match(item['description']):
                    skip_to = i + 1  # don't skip next item
                    continue
                else:
                    raise ValueError("unforeseen edge case")
            elif float(amount) < 0:
                # Usually a discount
                continue
            else:
                purchase = PurchaseItem(**item)
            purchases.append(purchase)

        return cls(items=purchases, value=total_value, amount_paid=amount_paid)


PATTERN_BIG_W_PARTNER = re.compile(r'\d{4} BIG W .+')


class Transaction(BaseModel, extra=Extra.allow):
    # N.B there's a lot of inconsistency across woolies' partners in how to store data; this class tries to handle that

    displayName: str  # e.g. '3127 Balwyn', 'Balwyn', 'Caltex Woolworths / EG Balwyn', '0368 BIG W Doncaster'
    storeName: str  # almost always the same as displayName
    storeNo: str  # e.g. '3127', '0'
    totalSpent: str  # e.g. '$11.40', '26.85'. Note: this is a misnomer; this is cost of items, not amount paid.
    totalPointsEarned: str  # e.g. '12', '38.00'
    date: str  # e.g. '16/02/2021'
    transactionDate: datetime  # e.g. 2020-08-04 18:39:23
    receiptKey: str  # e.g. 'U2FsdGVkX1+Q7oGFwGPJJxgRw...+GkBizWJbCu9QwZ+1+GFqM6/58w55k='
    basketKey: str  # 20200804183836062051773127 date|time|...|storeno

    @property
    def receipt(self) -> ReceiptDetails:
        receipt = self.__dict__.get('_receipt')
        if receipt is None:
            receipt = get_receipt(self.receiptKey)
            self.__dict__['_receipt'] = receipt
        return receipt

    @property
    def transaction_date(self) -> datetime:  # 2020-01-02T03:04:05+10:00
        return self.transactionDate.astimezone()

    @property
    def total_paid(self) -> Decimal:
        """ Amount paid; may vary from cost of items as gift-cards/discounts may be applied. """
        return self.receipt.amount_paid

    @property
    def is_big_w(self) -> bool:
        return PATTERN_BIG_W_PARTNER.match(self.displayName) is not None

#


def list_transactions(page: int = 0) -> Generator[List[Transaction], None, None]:
    """ Yields list ("page") of Transactions for global Woolies account """
    url = urljoin(endpoint, 'v1/rewards/member/ereceipts/transactions/list')
    while True:
        page += 1  # Endpoint indexes at 1
        response = session.get(url=url, params={"page": page})
        if not (data := response.json()['data']):
            return
        else:
            yield [Transaction.parse_obj(transaction) for transaction in data]


def get_receipt(receipt_key: str) -> ReceiptDetails:
    url = urljoin(endpoint, 'v1/rewards/member/ereceipts/transactions/details')
    body = {"receiptKey": receipt_key}
    response = session.post(url=url, json=body)
    return ReceiptDetails.from_raw(response.json()['data'])


#

if __name__ == '__main__':
    transactions = [y for x in list_transactions() for y in x]
    for trans in transactions:
        if trans.receiptKey != '':  # Ignore partners w/o receipt data
            print(trans.basketKey, trans.transaction_date, trans.total_paid, trans.json())
