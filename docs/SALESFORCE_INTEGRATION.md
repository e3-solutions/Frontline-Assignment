# Salesforce and carrier quote integration

The voice service reads loads from Supabase `public.loads` and linked `public.stops`, as described in [the load schema contract](KCH_SUPABASE_SCHEMA.md). It submits carrier quotes through the separate KCH carrier quote API, which creates Salesforce `rtms__CarrierQuote__c` records.

## Quote submission

`NegotiationDBService.notify_carrier_quote` uses `shared/src/kch_quote_client.py`. The client authenticates with Cognito client credentials and submits the load's business reference, quote amount, and carrier details to the carrier quote endpoint.

Configure the existing voice environment variables:

```dotenv
KCH_QUOTE_CLIENT_ID=your-development-client-id
KCH_QUOTE_CLIENT_SECRET=your-development-client-secret
KCH_QUOTE_SCOPE=your-development-scope
KCH_QUOTE_USE_SANDBOX=true
```

See [Carrier quote API usage](CARRIER_QUOTE_USAGE.md) and [the request contract](CARRIER_QUOTE_HANDOFF.md) for the endpoint and payload details.

## Shared compatibility utilities

`shared/src/salesforce_api.py` remains available as a direct Salesforce REST client. It exposes load lookup methods, token caching, and a single reauthentication retry after a 401 response. `shared/src/load_normalization.py` also supports historical `rtms__Load__c` records alongside the current Supabase load format.

The direct Salesforce client requires `SALESFORCE_TOKEN_URL`, `SALESFORCE_CLIENT_ID`, and `SALESFORCE_CLIENT_SECRET` when instantiated. These are separate from the Cognito credentials used for quote submission. The normal voice load lookup path does not instantiate this client.

Historical text load references and the normalization branches preserve compatibility with existing call and negotiation data.
