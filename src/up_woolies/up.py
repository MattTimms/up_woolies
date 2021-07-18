import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Generator, Any, Literal, Optional
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv
from prance import ResolvingParser
from pydantic import BaseModel, Extra, UUID4

from utils import parse_money

# Get token from environment variables
load_dotenv(dotenv_path='../../.env')

# Define endpoint & headers
endpoint = "https://api.up.com.au/api/v1/"
session = requests.session()
session.headers.update({
    "Authorization": f"Bearer {os.environ['UP_TOKEN']}"
})
session.hooks = {
    'response': lambda r, *args, **kwargs: r.raise_for_status()
}

parser = ResolvingParser("https://raw.githubusercontent.com/up-banking/api/master/v1/openapi.json")


# print(parser.specification)  # contains fully resolved specs as a dict


class Transaction(BaseModel, extra=Extra.allow):
    """ Dataclass for Up Transactions """

    class MoneyObject(BaseModel):
        currencyCode: str  # ISO 4217
        value: str  # '[-]10.56'
        valueInBaseUnits: str  # '[-]1056'

    id: UUID4
    status: Literal['SETTLED', 'HELD']
    rawText: Optional[str]
    description: str
    message: Optional[str]
    # holdInfo: Optional[...]
    # roundUp: Optional[...]
    # cashBack: Optional[...]
    amount: MoneyObject
    foreignAmount: Optional[MoneyObject]
    settledAt: Optional[datetime]
    createdAt: Optional[datetime]

    @classmethod
    def from_response(cls, response: Dict[str, Any]):
        return cls(id=response['id'], **response['attributes'])

    @property
    def value(self) -> Decimal:
        return parse_money(self.amount.value)


class Account:
    """ Base account class """

    def __init__(self, name: str):
        # Find account details by name
        for account in list_accounts():
            if name in account['attributes']['displayName']:
                break
        else:
            raise ValueError(f"could not find account {name=}")

        self.account = account
        self.transaction_url = account['relationships']['transactions']['links']['related']


class SpendingAccount(Account):
    name = "Up Account"

    def __init__(self):
        super().__init__(name=self.name)

    def get_transactions(self,
                         page_size: int = 10,
                         since: datetime = None,
                         until: datetime = None) -> Generator[List[Transaction], None, None]:
        """ Yields list of transactions based off input filters """
        response = session.get(url=self.transaction_url,
                               params={
                                   'page[size]': page_size,
                                   'filter[since]': since.astimezone().isoformat('T') if since is not None else since,
                                   'filter[until]': until.astimezone().isoformat('T') if until is not None else until,
                               }).json()
        yield [Transaction.from_response(transaction) for transaction in response['data']]

        # Continue with pagination link
        while (url := response['links']['next']) is not None:
            response = session.get(url=url).json()
            yield [Transaction.from_response(transaction) for transaction in response['data']]


#


def list_accounts() -> List[Dict[str, Any]]:
    return session.get(url=urljoin(endpoint, 'accounts')).json()['data']


if __name__ == '__main__':
    from collections import defaultdict

    up_account = SpendingAccount()
    grocery_retailers = defaultdict(list)
    for _transactions in up_account.get_transactions(page_size=100):
        for trans in _transactions:
            if (desc := trans.description) in ['Coles', 'Woolworths']:
                grocery_retailers[desc].append(trans)
                print(trans)
