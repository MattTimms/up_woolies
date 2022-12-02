import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Generator, Any, Literal, Optional
from urllib.parse import urljoin

import prance
from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel, Extra, UUID4

from utils import new_session, parse_money

# Get token from environment variables
load_dotenv(dotenv_path=find_dotenv())

# Define endpoint & headers
endpoint = "https://api.up.com.au/api/v1/"
session = new_session()
session.headers.update({
    "Authorization": f"Bearer {os.environ['UP_TOKEN']}"
})

parser = prance.ResolvingParser("https://raw.githubusercontent.com/up-banking/api/master/v1/openapi.json")


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


DEFAULT_PAGE_SIZE = 30


class Account:
    """ Base account class """

    def __init__(self, *,
                 display_name: str,
                 account_type: Literal['TRANSACTIONAL', 'SAVER'] = None,
                 ownership_type: Literal['INDIVIDUAL', 'JOINT'] = None):
        attributes = {k: v for k, v in {
            'displayName': display_name,
            'accountType': account_type,
            'ownershipType': ownership_type,
        }.items() if v is not None}

        # Find account details by name
        for account in list_accounts():
            if attributes.items() <= account['attributes'].items():
                break
        else:
            raise ValueError(f"could not find account matching {attributes=}")

        self.account = account
        self.transaction_url = account['relationships']['transactions']['links']['related']

    def get_transactions(self,
                         page_size: int = DEFAULT_PAGE_SIZE,
                         since: datetime = None,
                         until: datetime = None,
                         category: str = None) -> Generator[List[Transaction], None, None]:
        """ Yields list of transactions based off input filters """
        response = session.get(url=self.transaction_url,
                               params={
                                   'page[size]': page_size,
                                   'filter[since]': since.astimezone().isoformat('T') if since is not None else since,
                                   'filter[until]': until.astimezone().isoformat('T') if until is not None else until,
                                   'filter[category]': category
                               }).json()
        yield [Transaction.from_response(transaction) for transaction in response['data']]

        # Continue with pagination link
        while (url := response['links']['next']) is not None:
            response = session.get(url=url).json()
            yield [Transaction.from_response(transaction) for transaction in response['data']]


class SpendingAccount(Account):
    def __init__(self):
        super().__init__(display_name='Spending', account_type='TRANSACTIONAL', ownership_type='INDIVIDUAL')


class TwoUpAccount(Account):
    def __init__(self):
        super().__init__(display_name='2Up Spending', account_type='TRANSACTIONAL', ownership_type='JOINT')


class AllSpendingAccounts:
    """ Class for managing multiple transactional accounts; i.e. individual & joint accounts. """

    def __init__(self):
        self._accounts = [account for account in list_accounts()
                          if account['attributes']['accountType'] == 'TRANSACTIONAL']
        self._account_ids = [account['id'] for account in self._accounts]

    def get_transactions(self,
                         page_size: int = DEFAULT_PAGE_SIZE,
                         since: datetime = None,
                         until: datetime = None,
                         category: str = None) -> Generator[List[Transaction], None, None]:
        """
        Yields list of transactions based off input filters.

        Note: this method gets from all accounts & then filters down, unlike the base `Account` class which requests
        from the accounts transaction-url. Preliminary tests show this approach is faster than chaining individual
        account generators & guarantees ordered transactions.
        """
        response = session.get(url=urljoin(endpoint, 'transactions'),
                               params={
                                   'page[size]': page_size,
                                   'filter[since]': since.astimezone().isoformat('T') if since is not None else since,
                                   'filter[until]': until.astimezone().isoformat('T') if until is not None else until,
                                   'filter[category]': category
                               }).json()
        yield [Transaction.from_response(transaction)
               for transaction in response['data']
               if transaction['relationships']['account']['data']['id'] in self._account_ids]

        # Continue with pagination link
        while (url := response['links']['next']) is not None:
            response = session.get(url=url).json()
            yield [Transaction.from_response(transaction)
                   for transaction in response['data']
                   if transaction['relationships']['account']['data']['id'] in self._account_ids]


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
