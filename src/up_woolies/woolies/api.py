import os

import gql
from dotenv import find_dotenv, load_dotenv
from gql.transport.requests import RequestsHTTPTransport

from utils import new_session

# Get token from environment variables
load_dotenv(dotenv_path=find_dotenv())

# Define endpoint & headers
endpoint = "https://api.woolworthsrewards.com.au/wx/"
session = new_session()
session.headers.update({
    'client_id': '8h41mMOiDULmlLT28xKSv5ITpp3XBRvH',  # some universal client API ID key
    'User-Agent': 'up_woolies'  # some User-Agent
})
session.headers.update({'Authorization': f"Bearer {os.environ['WOOLIES_TOKEN']}"})

# Define GraphQL client
_endpoint_graphql = "https://apigee-prod.api-wr.com/wx/v1/bff/graphql"
_transport = RequestsHTTPTransport(url=_endpoint_graphql, verify=True, retries=3, headers=dict(session.headers))  # TODO
gql_client = gql.Client(transport=_transport, execute_timeout=5, serialize_variables=True)

# The ugly GraphQL query that's baked-in to Woolies' JS client
fetch_transaction_query = gql.gql(
    """
    query RewardsActivityFeed($nextPageToken: String!) {
      rtlRewardsActivityFeed(pageToken: $nextPageToken) {
        list {
          groups {
            ... on RewardsActivityFeedGroup {
              id
              title
              items {
                id
                displayDate
                description
                message
                displayValue
                displayValueHandling
                icon
                iconUrl
                transaction {
                  origin
                  amountAsDollars
                }
                highlights {
                  description
                  value
                }
                receipt {
                  receiptId
                  analytics {
                    partnerName
                  }
                }
                transactionType
                actionURL
              }
            }
          }
          nextPageToken
        }
      }
    }
    """
)
