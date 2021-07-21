# up_woolies

Proof-of-concept combining APIs to provide an itemised breakdown of transactions at Woolworths with Up Banking Account. 
The graphic below is a fantasy of how digital receipts could be presented in-app:

<p align="center">
  <img src="/imgs/demo.gif" width="35%" height="35%" />
</p>

## motivation

> _"My bank app tells me I spent $38.00 at the grocery store... I wonder what I bought..."_

I predict that banking apps will one-day provide customers with itemised receipts in-app.   
It's a big call but when I look into my crystal ball I see;

* Point-of-Sale and payment providers will manage the digital receipts/invoices of the transactions you've made with
  your bank card; no need for additional loyalty cards.
* Square, Tyro, Stripe, PayPal, etc. will offer secure APIs to pull invoice data as part of the
  [Consumer Data Rights (CDR)](https://www.cdr.gov.au/what-is-cdr) initiative.
* Banks, financial-wellbeing services, & other FinTechs will bridge invoice data with banking data - thanks to
  [Open Banking](https://www.ausbanking.org.au/priorities/open-banking/) & CDR.

The FinTech space is generating a lot of interesting products around the idea of financial-wellness. Up, Douugh, Frollo,
WeMoney, and other platforms offer tools to track spending habits - some using "AI" & data-driven tools to help
consumers. Surely, these platforms would benefit from having greater granularity to purchases; it is hard to distinguish
purchase behaviour from knowing only the vendor & not the items.

I wanted to make a proof-of-concept using Up Bank's well-documented API & one of, if not the largest Australian grocers:
Woolworths. In short, Woolworths API is closed-source & painful to look at. However, they do provide customers with
e-receipts, which is more than I can say for their competitor, Coles' FlyBuy program.

## requirements

* You're an [Upsider](https://up.com.au/) ⚡
    * You have an account with Up Bank & you've used this to purchase from Woolworths.
* You have an [Everyday Rewards](https://www.woolworthsrewards.com.au/) account
    * Which you've remembered to use when purchasing from Woolworths with your Up Bank account.

## getting started

1. Head to [Up Banking's API](https://developer.up.com.au/#welcome) page & grab your personal API token
2. Login to [Woolworth's Everyday Rewards](https://www.woolworthsrewards.com.au/#login) site & navigate around with
   dev-tools monitoring network traffic. Filter network traffic with `api.woolworthsrewards.com.au` & find any request
   that has `client_id` & `authorization` headers.  
   N.B. the authorization bearer token expires after 30 minutes; you'll need to repeat the process if that occurs. It's
   pretty frustrating but if you think you can help improve this please [help wanted](#help-wanted) section & reach out.
3. Copy `.env.example` to `.env` & place those three tokens inside:
    ```
   WOOLIES_CLIENT_ID=1234abcd...
   WOOLIES_TOKEN=1234abcd...
   UP_TOKEN=up:yeah:1234abcd...
   ```
4. Look around & run some scripts, you crazy kids!

## help wanted

I'm holding out for Up Bank to provide API support for 2Up (& multiplayer when that is released). You can help by
reacting to the pending [feature request PR](https://github.com/up-banking/api/issues/84) and, if you're an Upsider,
suggest the feature through support chat in-app 🙏

I'd love help with handling Woolworth's authentication process 🔐 I spent quite some time trying to understand how
Woolworth's authentication endpoint operates - reading client-side js files, figuring out their device-fingerprint
workflow, trying to see if it matches up with some common OAuth practice.  
Obtaining a user's `client_id` & `bearer token` via `accounts.woolworthsrewards.com.au/er-login/validate-user` from
their `email` & `pass` is the ultimate goal. Any help would be great; I'd love to learn how that works.

## the graveyard of future ideas

* Support OpenBanking API - _aka_ support for all banks!
    * I noticed a purchase that I made with Westpac rather than Up, and after looking through Frollo & CDR I realised
      that many more banks had begun supporting the Open Banking initiative.
    * Unfortunately, despite its affiliation with _"Consumer Data Rights"_, the process of authenticating myself with
      these CDR data holders for my _own_ consumer data is a mystery to me. If you know, then please reach out to me.
* Support 2Up
    * Please read [help wanted](#help-wanted) on how you can help push for API support of 2Up.