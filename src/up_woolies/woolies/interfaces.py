import os
import re
import warnings
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Literal, Generator
from urllib.parse import urljoin

from dateutil.relativedelta import relativedelta
from pydantic import BaseModel, Extra, condecimal, PositiveInt

from .api import session, endpoint, gql_client, fetch_transaction_query
from utils import parse_money


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
    value: Decimal  # Value of items purchased
    amount_paid: Decimal  # Amount paid by card/cash (considering gift-cards &/or other discounts)
    date: Optional[datetime]  # Datetime of payment transaction

    class Config:
        fields = {'value': {'exclude': True}}

    @classmethod
    def get_receipt(cls, receipt_key: str):
        url = urljoin(endpoint, 'v1/rewards/member/ereceipts/transactions/details')
        body = {"receiptKey": receipt_key}
        response = session.post(url=url, json=body)
        return ReceiptDetails.from_raw(response.json()['data'])

    @classmethod
    def from_raw(cls, response: Dict[str, Any]):
        """
        Returns class by parsing multi-line items from e-receipt response.
        Certain purchases express themselves across multiple lines in the receipt; i.e. purchases of duplicate items,
        or weighted goods. They are parsed to return self's items attribute where each purchased item may have

        :param response: data response from receipt endpoint; i.e. the return from get_receipt().
        """
        receipt_details_dict: Dict[str, Any] = {x['__typename']: x for x in response['receiptDetails']['details']}

        # Parse transaction payment datetime
        transaction_date = None
        if (date_raw := re.search('POS\s{2}\d{3}\s{2}TRANS\s{2}\d{4}\s{3}(.+)',
                                  receipt_details_dict['ReceiptDetailsFooter']['transactionDetails'])) is not None:
            transaction_date = datetime.strptime(date_raw.groups()[0], '%H:%M  %d/%m/%Y')

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

        return cls(items=purchases, value=total_value, amount_paid=amount_paid, date=transaction_date)


_two_months_ago = datetime.today() - relativedelta(months=2)


class Transaction(BaseModel, extra=Extra.allow):
    id: str
    origin: str  # Store Name, e.g. 'Blackburn North', 'Doncaster Shopping Town BWS'
    value: Decimal  # '11.40'
    date: datetime  # Note this may vary from eftpos transaction date by several minutes
    description: str  # '$11.40 at Blackburn North'
    receiptId: Optional[str]  # Note some partners do not support e-receipts; e.g. EG petrol
    transactionType: str  # 'purchase' there could be others
    partner: Literal['woolworths', 'bws', 'bigw', 'eg', 'eg_ampol', 'caltex_woolworths']  # there could be others
    rewardsPointsEarned: str  # EveryDay Reward Points '+ 44 pts'
    raw: Dict[str, Any]

    @staticmethod
    def list_transactions() -> Generator[List['Transaction'], None, None]:
        """ Yields page list of Transactions for Woolies account """
        next_page_token = "FIRST_PAGE"
        while True:
            data = gql_client.execute(fetch_transaction_query, variable_values={'nextPageToken': next_page_token})
            if not data:
                return
            else:
                yield [
                    Transaction.from_response(data=item, group_title=months_transactions['title'])
                    for months_transactions in data['rtlRewardsActivityFeed']['list']['groups']
                    for item in months_transactions['items']
                ]
                if (next_page_token := data['rtlRewardsActivityFeed']['list']['nextPageToken']) is None:
                    return

    @classmethod
    def from_response(cls, data: Dict[str, Any], group_title: str):

        # Attempt Woolworth's partner identification
        if (partner := data['icon']) == 'unknown_partner':
            basename = os.path.basename(data['iconUrl'])
            partner, *_ = basename.split('_logo.png')[0].split('_division')
            if partner == 'supermarkets':
                partner = 'woolworths'

        # Get _rough_ transaction date
        id_ = data['id']
        if re.match(r'S\d{4}W\d{3}SN\d{4}T\d{10}', id_):  # 'S3060W084SN2594T1667017441' store|...|date
            transaction_date = datetime.fromtimestamp(int(id_[-10:]))
        elif re.match(r'^\d+$', date_str := id_[:20]):  # '20200804183836062051773127' date|time|...|storeno
            transaction_date = datetime.strptime(date_str, '%Y%m%d%H%M%S%f')
        else:
            transaction_date = datetime.strptime(data['displayDate'], '%a %d %b')
            transaction_date = transaction_date.replace(year=_two_months_ago.year)
            if _two_months_ago < transaction_date and group_title not in ['This Month', 'Last Month']:
                transaction_date -= relativedelta(years=1)

        return cls(
            id=data['id'],
            date=transaction_date,
            description=data['description'],
            origin=data['transaction']['origin'],
            value=data['transaction']['amountAsDollars'].replace('$', ''),
            receiptId=data['receipt']['receiptId'] if data['receipt'] is not None else None,
            partner=partner,
            transactionType=data['transactionType'],
            rewardsPointsEarned=data['displayValue'],
            raw=data
        )

    def amount_paid(self) -> Decimal:
        """ Amount paid; may vary from cost of items due to gift-cards/discounts at checkout """
        return self.receipt().amount_paid

    def receipt(self) -> ReceiptDetails:
        # Lazy-load receipt
        if (_receipt := self.__dict__.get('_receipt')) is None:
            _receipt = ReceiptDetails.get_receipt(self.receiptId)
            self.__dict__['_receipt'] = _receipt
        return _receipt

    @property
    def has_receipt(self) -> bool:
        return self.receipt is not None

    @property
    def display_name(self) -> str:
        return self.origin


if __name__ == '__main__':
    transactions: List[Transaction] = [y for x in Transaction.list_transactions() for y in x]
    for trans in transactions:
        if not trans.has_receipt:  # Ignore partners w/o receipt data
            print(trans.id, trans.date, trans.value, trans.json())
