import datetime
import json
import time

from rich import print

import up
import woolies


up_accounts = up.AllSpendingAccounts()


def find_corresponding_up_transaction(woolies_transaction: woolies.Transaction) -> up.Transaction:
    """ Returns corresponding Up Bank transaction from a Woolies transaction"""
    _up_category = 'groceries'
    _up_description = 'Woolworths'  # How Up manages human-readable merchant Id for Woolworths

    # Request transactions within window of the Woolies transaction
    transaction_datetime = woolies_transaction.transaction_date
    for up_transactions in up_accounts.get_transactions(since=transaction_datetime - datetime.timedelta(seconds=10),
                                                        until=transaction_datetime + datetime.timedelta(seconds=10),
                                                        category=_up_category):
        for up_transaction in up_transactions:
            # Validate transactions match
            is_merchant_woolies = up_transaction.description == _up_description
            is_money_spent_equal = up_transaction.value == woolies_transaction.total_paid
            if is_merchant_woolies and is_money_spent_equal:
                return up_transaction
        else:
            continue
    else:
        raise FileNotFoundError("could not find corresponding transaction with up bank")


def example():

    for transactions in woolies.list_transactions():
        for woolies_transaction in transactions:

            # Filter out Woolworth partners
            if woolies_transaction.receiptKey == '':
                print("ignoring partner transaction", woolies_transaction.displayName,
                      woolies_transaction.transaction_date)
                continue

            # Find Up transaction
            try:
                up_transaction = find_corresponding_up_transaction(woolies_transaction)
            except FileNotFoundError:
                print("couldn't find an Up Banking transaction", woolies_transaction.transaction_date)
                continue

            # Grab receipt and show
            woolies_receipt = woolies_transaction.receipt

            # Print it but make it pretty
            print({'date': up_transaction.createdAt.astimezone().isoformat('T'), **json.loads(woolies_receipt.json())})


if __name__ == '__main__':
    example()
