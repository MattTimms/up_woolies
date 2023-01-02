# v1.3.1 - 03/01/2023

- Added an MIT License

# v1.3.0 - 02/12/2022

Woolies API replaced the REST API endpoint for fetching transactions with a GraphQL API endpoint which provides similar
but different information. This release adds support for this new endpoint. Note, Woolies will store transactions for
only 14 months.

- Added better support of Woolies' partners' e-receipts; i.e. BigW, BWS
- Changed woolies transaction interface models
- Fixed support for Woolies ✨new✨ API
- Depreciated woolies-auth code

## v1.2.0 - 10/04/2022

- Added support for 2-up & multiplayer 💕 (multiple transactional accounts)
- Added request retries & exponential back-off
- Fixed incorrect comparison value; amount-paid now preferred over cost-of-items, to address gift-cards & discounts
- Fixed receipt-parsing for a few unseen edge-cases; i.e. price-reduced items

## v1.1.0 - 20/02/2022

- Added changelog 📑
- ~~Added Woolworth's email:password login via env. vars. or CLI~~
    - Nevermind, the woolies' login endpoint shared via [#1](https://github.com/MattTimms/up_woolies/issues/1) has begun
      rejecting requests & instead returns 403 forbidden
- Added use of Up API's category-filter for off-loading some filtering compute to them
- Added python rich library for prettier print-outs
- Added scaffolding for accessing 2Up data
- Updated README
- Fixed missing/new requirement for `User-Agent` header for Woolworth's API
- Fixed default Up spending account name from `Up Account` to `Spending` as per
  💕 [2Up Support](https://github.com/up-banking/api/issues/31#issuecomment-1008441619) update
- Fixed indefinite requests with default timeout adapter on request sessions
- Fixed missing dependency versions

## v1.0.0 - 24/07/2021

- ⚡ initial release