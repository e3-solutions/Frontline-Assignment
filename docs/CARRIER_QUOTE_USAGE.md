# Carrier quote API — usage (automation and agents)

This document describes how to authenticate and call the **create carrier quote** HTTP endpoint. The implementation creates a Salesforce **`rtms__CarrierQuote__c`** record after resolving the load, account, and carrier service in the TMS.

---

## Endpoint

| Item | Value |
|------|--------|
| **URL** | `https://agent.kch-api-services.net/carrier_quote` |
| **Method** | `POST` only (`GET` and others return **405**). |
| **Headers** | `Content-Type: application/json` and `Authorization: Bearer <access_token>`. |
| **Body** | JSON object (UTF-8). Plain JSON in the request body is required (base64-wrapped bodies are not supported). |

Always use TLS (`https://`).

---

## Authentication

Edge protection (for example API Gateway with a Cognito JWT authorizer) requires a valid **Bearer** token on every request.

### Get an access token (client credentials)

1. **POST** to:

   `https://kch-m2m.auth.us-east-2.amazoncognito.com/oauth2/token`

2. **Header:** `Content-Type: application/x-www-form-urlencoded`

3. **Body (form):** `grant_type=client_credentials` plus **`client_id`**, **`client_secret`**, and **`scope`** as required by your machine-to-machine app client.

4. **Parse** JSON response fields: **`access_token`**, **`expires_in`**, **`token_type`**.

5. **Call the API** with `Authorization: Bearer <access_token>`.

Do not embed **`client_secret`** in prompts or committed code; use secrets management or environment configuration. Renew the token before **`expires_in`** elapses.

### Token request (curl)

```bash
curl -X POST "https://kch-m2m.auth.us-east-2.amazoncognito.com/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=<client_id>&client_secret=<client_secret>&scope=<scope>"
```

### Call the carrier quote endpoint (curl)

```bash
curl -X POST "https://agent.kch-api-services.net/carrier_quote" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -d @payload.json
```

---

## Request JSON shape

Send a single JSON object. Field names are **camelCase** as below.

### Required

| Field | Type | Description |
|--------|------|-------------|
| `loadId` | string | Exact `rtms__Load__c.Name` in Salesforce. |
| `amount` | number | Quote amount. Omitting `amount` or using JSON `null` is invalid (use a numeric value, including `0` if required). |
| `carrier` | object | Must be present with **at least one** non-empty string: `mcNumber` or `dotNumber` (whitespace-only counts as empty). Drives account lookup before fallback. |

### Optional — environment routing

| Field | Type | Description |
|--------|------|-------------|
| `useSandbox` | boolean | If present, selects Salesforce **sandbox** (`true`) or **production** (`false`) for this request only. If **omitted**, the server falls back to env `SALESFORCE_USE_SANDBOX` (treated as true only when set to the string `true`, case-insensitive); otherwise production is used. |

Prefer setting `useSandbox` explicitly when the caller must target sandbox vs production.

### Optional — extended payload

| Field | Type | Description |
|--------|------|-------------|
| `notes` | string | Part of `rtms__Messages__c` (concatenated with `url`). |
| `url` | string | Appended after a newline in `rtms__Messages__c`. |
| `metadata` | object | Optional `transportationMode` (string); see below. |
| `source` | object | Bid/source parties; see nested shape below. |

**`metadata.transportationMode`**

If non-empty, must **exactly** match a `rtms__Mode__c.Name` (same values as on the load). Allowed values (case- and punctuation-sensitive):

`Air Freight`, `Bulk`, `Drayage`, `Flatbed`, `Intermodal`, `LTL`, `Ocean FCL`, `Ocean LCL`, `Open Deck`, `Parcel`, `Power Only`, `Reefer`, `Van`, `Warehouse`, `YOHLER`

Example:

```json
{ "transportationMode": "Van" }
```

**`source`** (all subfields optional unless needed)

- `sourceType` — if present and non-empty, must be exactly one of: **`bmt`**, **`call`**, **`email`**, **`platform`**, **`sms`** (maps to Salesforce `SourceType__c`; use **`call`** for phone/voice-style flows).
- `id`, `direction` (strings)
- `fromParty`, `toParty`: objects with optional `partyType`, `email`, `name`, and `phone` (`e164Number`, `extension`)

**`carrier`** (object required on every request)

- **`mcNumber` and/or `dotNumber`** — at least one must be a non-empty string (after trim). Other `carrier` keys are optional.
- `companyName`, `email` (strings)
- `phone`: `{ "e164Number": "...", "extension": "..." }`
- `compliance`: only `hwIsCarrierChannelVerified` (boolean) is written to Salesforce today (`Highway_Phone_Verification__c`).

**MC normalization (server-side):** if `mcNumber` is present and does not already start with `MC`, the server prefixes `MC` for the **account** SOQL lookup. The raw `mcNumber` may still be sent on the quote as a potential-carrier field.

---

## Example requests

**Minimal (production unless env says otherwise):**

```http
POST /carrier_quote HTTP/1.1
Host: agent.kch-api-services.net
Content-Type: application/json
Authorization: Bearer <ACCESS_TOKEN>

{
  "loadId": "LOAD-12345",
  "amount": 2500.00,
  "carrier": { "mcNumber": "123456" }
}
```

**Explicit sandbox + carrier and metadata:**

```json
{
  "loadId": "LOAD-12345",
  "amount": 2500.00,
  "useSandbox": true,
  "notes": "Bid from board",
  "url": "https://example.com/bid/abc",
  "metadata": { "transportationMode": "Van" },
  "carrier": {
    "mcNumber": "123456",
    "dotNumber": "987654",
    "compliance": { "hwIsCarrierChannelVerified": true }
  },
  "source": {
    "sourceType": "call",
    "fromParty": {
      "partyType": "carrier",
      "name": "Example Logistics",
      "email": "dispatch@example.com",
      "phone": { "e164Number": "+15551234567", "extension": "" }
    }
  }
}
```

---

## Success response

- **Status:** `201 Created`
- **Body:** JSON

```json
{ "id": "<Salesforce rtms__CarrierQuote__c Id>" }
```

Treat `id` as the system of record for the new quote.

---

## Error responses

Errors use JSON with stable `code` and human-readable `message`:

```json
{
  "code": "LOAD_NOT_FOUND",
  "message": "Load not found with Name: LOAD-xyz"
}
```

| HTTP | `code` | When |
|------|--------|------|
| 400 | `INVALID_JSON` | Body is not valid JSON. |
| 400 | `INVALID_REQUEST` | Base64-encoded body flag set (not supported here). |
| 400 | `VALIDATION_ERROR` | Missing `loadId` or `amount`, missing `carrier` / both `mcNumber` and `dotNumber` empty, invalid `source.sourceType`, or invalid `metadata.transportationMode`. |
| 405 | `METHOD_NOT_ALLOWED` | Not `POST`. |
| 404 | `LOAD_NOT_FOUND` | No `rtms__Load__c` with matching `Name`. |
| 404 | `NO_CARRIER_ACCOUNT` | No account resolved from MC/DOT/fallback. |
| 404 | `NO_CARRIER_SERVICE` | No matching enabled carrier service for the profile/mode. |
| 500 | `CONFIG_ERROR` | Server misconfiguration (e.g. missing fallback account id). |
| 500 | `SALESFORCE_CLIENT_ERROR` | Could not initialize Salesforce client. |
| 500 | `QUERY_ERROR` | SOQL or transport error during lookup. |
| 500 | `CREATE_FAILED` | Salesforce rejected the insert. |

**Agent behavior:** on 4xx, fix the payload or referenced TMS data (load, carrier identifiers). On 5xx, retry only if appropriate for your orchestration policy; do not assume idempotency—duplicate posts may create duplicate quotes unless you add a separate idempotency layer.

---

## Checklist

1. Obtain a valid **Bearer** token via Cognito client credentials; send **`Authorization: Bearer …`** on every request.
2. Confirm `loadId` matches an existing load **Name** in the target org (sandbox vs prod per `useSandbox`).
3. Always send a numeric `amount`.
4. Always send `carrier` with at least one of `mcNumber` or `dotNumber` populated.
5. Set `useSandbox` when the task is explicitly against sandbox; omit only if relying on server env defaults.
6. Parse error `code` for programmatic branching; show `message` to humans or logs.
