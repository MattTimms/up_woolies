import os
import re
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Generator, Optional
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Extra, condecimal, PositiveInt

from utils import parse_money

# Get token from environment variables
load_dotenv(dotenv_path='./.env')

# Define endpoint & headers
endpoint = "https://api.woolworthsrewards.com.au/wx/v1/"
session = requests.session()
session.headers.update({
    'client_id': os.environ['WOOLIES_CLIENT_ID'],
    'Authorization': f"Bearer {os.environ['WOOLIES_TOKEN']}"
})
session.hooks = {
    'response': lambda r, *args, **kwargs: r.raise_for_status()
}


# TODO support for Woolies' partners e.g. BWS, BigW, etc


class Purchase(BaseModel, extra=Extra.ignore):
    """ Dataclass of an unique purchased item """
    description: str
    amount: condecimal(gt=Decimal(0), decimal_places=2)
    quantity: Optional[PositiveInt] = 1
    weight: Optional[condecimal(gt=Decimal(0))]

    # TODO parse description for weight e.g. {'description': 'Abbotts Vil Bakery Country Grains 800g'}
    # TODO remove leading symbols from description e.g. {'description': '#Cadbury Bar Twirl 39g'}
    # TODO what if I purchase two weighted goods separately in one transaction; I went back to the deli for more olives?


class ReceiptDetails(BaseModel):
    """ Parsed-receipt items for a single transaction """
    # N.B. everything you see on a physical receipt is available from Woolies API
    items: List[Purchase]

    @classmethod
    def from_raw(cls, response: Dict[str, Any]):
        """
        Returns class by parsing multi-line items from e-receipt response.
        Certain purchases express themselves across multiple lines in the receipt; i.e. purchases of duplicate items,
        or weighted goods. They are parsed to return self's items attribute where each purchased item may have

        :param response: data response from receipt endpoint; i.e. the return from get_receipt().
        """
        # Navigate down to the response's receipt detail items
        receipt_detail_items = next(filter(lambda x: x['__typename'] == 'ReceiptDetailsItems',
                                           response['receiptDetails']['details']))
        items: List[Dict[str, Any]] = receipt_detail_items['items']  # Note: list is ordered for purchase readability

        skip_to = 0
        purchases: List[Purchase] = []
        pattern_multiple = re.compile(r'Qty (\d+) @ \$\d+\.\d+ each')  # e.g. 'Qty 2 @ $6.00 each'
        pattern_weighted = re.compile(r'(\d+\.\d+) kg NET @ \$\d+\.\d+/kg')  # e.g. '0.716 kg NET @ $4.00/kg'

        # Parse receipt items
        for i, item in enumerate(items):
            if i < skip_to:
                continue

            # Handle multi-line receipt item
            if item['amount'] == '':
                skip_to = i + 2

                next_item = items[i + 1]

                # Handle purchase of multiple identical items
                if pattern_multiple.match(next_item_desc := next_item['description']):
                    quantity = pattern_multiple.findall(next_item_desc)[0]
                    purchase = Purchase(description=item['description'],
                                        amount=next_item['amount'],
                                        quantity=quantity)

                    # Amend for any discounts for multiple identical items purchased
                    if i + 2 < len(items):
                        potential_discount_amount = items[i + 2]['amount']
                        if potential_discount_amount and (future_item_amount := Decimal(potential_discount_amount)) < 0:
                            purchase.amount += future_item_amount
                            skip_to += 1

                # Handle purchase of weighted item; e.g. fruit, veg, & deli
                elif pattern_weighted.match(next_item_desc):
                    weight = pattern_weighted.findall(next_item_desc)[0]
                    purchase = Purchase(description=item['description'],
                                        amount=next_item['amount'],
                                        weight=weight,
                                        quantity=None)

                else:
                    raise  # unforeseen edge case
            else:
                purchase = Purchase(**item)
            purchases.append(purchase)

        return cls(items=purchases)


class Transaction(BaseModel, extra=Extra.allow):
    # N.B there's a lot of inconsistency across woolies' partners in how to store data; this class tries to handle that

    displayName: str  # e.g. '3127 Balwyn', 'Balwyn', 'Caltex Woolworths / EG Balwyn'
    storeName: str  # almost always the same as displayName
    storeNo: str  # e.g. '3127', '0'
    totalSpent: str  # e.g. '$11.40', '26.85'
    totalPointsEarned: str  # e.g. '12', '38.00'
    date: str  # e.g. '16/02/2021'
    transactionDate: str  # e.g. 2020-08-04 18:39:23
    receiptKey: str  # e.g. 'U2FsdGVkX1+Q7oGFwGPJJxgRw...+GkBizWJbCu9QwZ+1+GFqM6/58w55k='
    basketKey: str  # 20200804183836062051773127 date|time|...|storeno

    def get_receipt(self) -> ReceiptDetails:
        return get_receipt(self.receiptKey)

    @property
    def transaction_date(self) -> datetime:  # 2020-01-02T03:04:05+10:00
        return datetime.strptime(self.transactionDate, '%Y-%m-%d %H:%M:%S').astimezone()

    @property
    def value(self) -> Decimal:
        return parse_money(self.totalSpent)


#


def list_transactions(page: int = 0) -> Generator[List[Transaction], None, None]:
    """ Yields list of Transactions for global Woolies account """
    url = urljoin(endpoint, 'rewards/member/ereceipts/transactions/list')
    while True:
        page += 1  # Endpoint indexes at 1
        response = session.get(url=url, params={"page": page})
        if not (data := response.json()['data']):
            return
        else:
            yield [Transaction.parse_obj(transaction) for transaction in data]


def get_receipt(receipt_key: str) -> ReceiptDetails:
    url = urljoin(endpoint, 'rewards/member/ereceipts/transactions/details')
    body = {"receiptKey": receipt_key}
    response = session.post(url=url, json=body)
    return ReceiptDetails.from_raw(response.json()['data'])


if __name__ == '__main__':
    transactions = [y for x in list_transactions() for y in x]
    for trans in transactions:
        if trans.receiptKey != '':  # Ignore partners w/o receipt data
            trans.get_receipt()
            print(trans.basketKey, trans.transactionDate, trans)
