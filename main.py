# get woolies transactions
# find them in up
# line by line it baby
import datetime

import up
import woolies


def find_corresponding_up_transaction(woolies_transaction: woolies.Transaction) -> up.Transaction:
    _up_description = 'Woolworths'  # How Up manages human-readable merchant Id for Woolworths

    transaction_datetime = woolies_transaction.transaction_date
    for up_transactions in up_account.get_transactions(until=transaction_datetime + datetime.timedelta(seconds=10),
                                                       since=transaction_datetime - datetime.timedelta(seconds=10)):
        for up_transaction in up_transactions:
            # Validate transactions match
            is_merchant_woolies = up_transaction.description == _up_description
            is_money_spent_equal = up_transaction.value == woolies_transaction.value
            if is_merchant_woolies and is_money_spent_equal:
                return up_transaction
        else:
            continue
    else:
        raise FileNotFoundError("could not find corresponding transaction with up bank")


if __name__ == '__main__':

    up_account = up.SpendingAccount()

    for transactions in woolies.list_transactions():
        for woolies_transaction in transactions:

            # Filter out Woolworth partners
            if woolies_transaction.receiptKey == '':
                print("ignoring partner transaction", woolies_transaction.displayName,
                      woolies_transaction.transaction_date)
                continue

            try:
                up_transaction = find_corresponding_up_transaction(woolies_transaction)
            except FileNotFoundError:
                print("couldn't find an Up Banking transaction", woolies_transaction.transaction_date)
                continue

            woolies_receipt = woolies_transaction.get_receipt()
            print("bingo", up_transaction.createdAt, woolies_receipt.json())
            print(1)

            # transaction_datetime = transaction.transaction_date()
            #
            # response = up_account.get_transactions(until=transaction_datetime + datetime.timedelta(seconds=1),
            #                                        since=transaction_datetime)
            # print(1)
            # response = requests.get(url=up_account.transaction_url,
            #                         params={
            #                             'page[size]': 100,
            #                             'filter[since]': transaction.transaction_date(),
            #                             # 'filter[until]':
            #                         },
            #                         )
            # response.raise_for_status()
