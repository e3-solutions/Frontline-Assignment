# Carrier quote API — hand-off guide

This service creates a **carrier quote** in the TMS (Salesforce object `rtms__CarrierQuote__c`). You send a JSON payload describing the load, price, and optional carrier or source details; the API looks up the load, resolves the account and carrier service, then inserts the quote. The flow is aligned with the legacy Fleetworks-style integration into the same TMS objects.

---

## Endpoint and usage

Use **HTTPS** and **POST** only:

**`https://agent.kch-api-services.net/carrier_quote`**

Other HTTP methods return **405**. Send a JSON body with:

```http
Content-Type: application/json
Authorization: Bearer <access_token>
```

The access token is obtained as described in [Authentication](#authentication) below.

---

## Authentication

Requests to `agent.kch-api-services.net` are protected at the edge (for example API Gateway with a **Cognito** JWT authorizer). Every call to **`/carrier_quote`** must include a valid **Bearer** access token:

```http
Authorization: Bearer <access_token>
```

### Machine-to-machine (client credentials)

For service-to-service access, use OAuth 2.0 **client credentials** against your Cognito user pool’s hosted domain (this deployment uses **`us-east-2`**).

1. **POST** to the token URL:

   `https://kch-m2m.auth.us-east-2.amazoncognito.com/oauth2/token`

2. **Headers:** `Content-Type: application/x-www-form-urlencoded`

3. **Body (form):** include at minimum:

   - `grant_type=client_credentials`
   - `client_id` — Cognito app client id for the M2M client
   - `client_secret` — matching secret (treat as confidential)
   - `scope` — space-separated scope string required by that app client (must match what Cognito expects for the resource server)

4. **Response:** JSON with `access_token`, `expires_in` (seconds), and `token_type` (typically `Bearer`).

5. Send that **`access_token`** in the **`Authorization: Bearer …`** header on **`POST /carrier_quote`**.

Cache or refresh tokens using **`expires_in`** so requests do not fail with expired credentials. Load **`client_secret`** from a secrets manager or environment variable; do not commit it to source control or embed it in shared prompts.

### Example: token request

```bash
curl -X POST "https://kch-m2m.auth.us-east-2.amazoncognito.com/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=<client_id>&client_secret=<client_secret>&scope=<scope>"
```

### Example: token response

```json
{
  "access_token": "<ACCESS_TOKEN>",
  "expires_in": 3600,
  "token_type": "Bearer"
}
```

### Example: create quote

```bash
curl -X POST "https://agent.kch-api-services.net/carrier_quote" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -d '{"loadId":"LOAD-12345","amount":2500,"carrier":{"mcNumber":"123456"}}'
```

---

## What you must include

Every request needs:

- **`loadId`** — The load’s **Name** in Salesforce, exactly as stored (not necessarily the same as an internal database id elsewhere).
- **`amount`** — The carrier total for the quote (a number). This is required; if you leave it out or send JSON `null`, the API returns a validation error.
- **`carrier`** — An object that includes **at least one** non-empty identifier: **`mcNumber`** or **`dotNumber`** (whitespace-only values do not count). Both may be sent if you have them. This is required so the API can resolve the carrier account in Salesforce before any fallback logic.

Together, those three pieces are the **smallest valid** request; everything else is optional.

---

## Sandbox vs production

Salesforce has separate **production** and **sandbox** orgs. You can steer which one is used **per request** with an optional boolean:

- **`useSandbox`: `true`** — use the sandbox org for this call only.
- **`useSandbox`: `false`** — use production for this call.

If you omit **`useSandbox`**, the server uses its own configuration (`SALESFORCE_USE_SANDBOX` environment variable): when that is set to the string `true` (case-insensitive), sandbox is used; otherwise production.

**Tip:** When testing, set `"useSandbox": true` explicitly so you are not surprised by environment defaults.

---

## All request body fields

All names below are **JSON keys** (camelCase). Omitted keys are simply not used; empty strings are allowed unless noted.

### Top level

| Field | Required | Type | What it does |
|--------|----------|------|----------------|
| `loadId` | Yes | string | Load identifier: must match **`rtms__Load__c.Name`** in Salesforce for the org you are calling (sandbox or production). |
| `amount` | Yes | number | Total for the carrier quote; stored on the quote record. Must be present (cannot be `null`). |
| `useSandbox` | No | boolean | If set, chooses Salesforce **sandbox** (`true`) or **production** (`false`) for this request. If omitted, the server uses its env default (see [Sandbox vs production](#sandbox-vs-production)). |
| `notes` | No | string | First part of the quote’s combined message field. |
| `url` | No | string | Appended after a newline following `notes` in the quote’s message field. |
| `metadata` | No | object | See [metadata](#metadata) below. |
| `carrier` | Yes | object | Must include at least one of **`mcNumber`** or **`dotNumber`** with a non-empty value. See [carrier](#carrier). |
| `source` | No | object | See [source](#source) below. |

### `metadata`

Single nested object. All keys are optional.

| Field | Type | What it does |
|--------|------|----------------|
| `transportationMode` | string | If non-empty, overrides the transportation mode used to find a carrier service. The value must **exactly match** a **`rtms__Mode__c.Name`** in Salesforce (same strings as **`rtms__Load__c.rtms__Mode_Name__c`** on the load). If empty or `metadata` is omitted, the API uses the load’s mode from Salesforce. |

**Allowed `transportationMode` values** (from `rtms__Mode__c.Name` in the org; case- and punctuation-sensitive):

`Air Freight`, `Bulk`, `Drayage`, `Flatbed`, `Intermodal`, `LTL`, `Ocean FCL`, `Ocean LCL`, `Open Deck`, `Parcel`, `Power Only`, `Reefer`, `Van`, `Warehouse`, `YOHLER`

If your org adds or renames modes, server validation must be updated to match.

### `carrier`

Required object. You must supply **at least one** of **`mcNumber`** or **`dotNumber`** as a non-empty string (after trimming spaces). The API tries MC-based account lookup first, then DOT, then a configured fallback account if neither matches.

| Field | Type | What it does |
|--------|------|----------------|
| `mcNumber` | string | Motor carrier number (optional only if `dotNumber` is provided instead). For **lookup**, if the value does not already start with `MC`, the server adds that prefix when querying accounts. The value can also be copied onto the quote as a “potential carrier” field (raw, without forcing that prefix). |
| `dotNumber` | string | USDOT number (optional only if `mcNumber` is provided instead). Used for account lookup when MC does not match. |
| `companyName` | string | Accepted in JSON; **not** copied onto the quote by this service (handy for logging or future use). |
| `email` | string | Accepted in JSON; **not** copied onto the quote by this service (use `source.fromParty` if you need email on the quote). |
| `phone` | object | Accepted in JSON; **not** copied onto the quote by this service (use `source.fromParty.phone` for potential carrier phone on the quote). |
| `compliance` | object | Optional **Highway**-style compliance block; see [compliance](#compliance). |

#### `compliance`

Nested under `carrier`. You may send the full set of fields for upstream parity; **only one is written to Salesforce today**.

| Field | Type | What it does |
|--------|------|----------------|
| `hwIsCarrierChannelVerified` | boolean (or null) | If `true`, sets the quote’s phone verification flag; if absent or false, treated as not verified. |
| `hwConnectionStatus` | string | Accepted; not written to the quote by this API. |
| `hwRulesAssessment` | string | Accepted; not written. |
| `hwIneligibleReason` | string | Accepted; not written. |

### `source`

Describes where the bid or call came from. All keys are optional.

| Field | Type | What it does |
|--------|------|----------------|
| `sourceType` | string | If set, must be one of **`bmt`**, **`call`**, **`email`**, **`platform`**, **`sms`** (maps to `SourceType__c`; case-sensitive). Omit or use an empty string if you do not want a source type on the quote. |
| `id` | string | Identifier for this source event. |
| `direction` | string | Direction label (e.g. inbound/outbound). |
| `fromParty` | object | “From” party; see [Party object](#party-object). Used for potential carrier name, email, phone on the quote when present. |
| `toParty` | object | “To” party; see [Party object](#party-object). Used for load-board source phone when present. |

### Party object

Used for `source.fromParty` and `source.toParty`.

| Field | Type | What it does |
|--------|------|----------------|
| `partyType` | string | Label for the party (e.g. carrier, broker). |
| `email` | string | Email for that party. |
| `name` | string | Display name. |
| `phone` | object | Optional; see [Phone object](#phone-object). |

### Phone object

Used under `carrier.phone`, `source.fromParty.phone`, and `source.toParty.phone`.

| Field | Type | What it does |
|--------|------|----------------|
| `e164Number` | string | Phone number in E.164 form (e.g. `+15551234567`) when available. |
| `extension` | string | Extension, if any. |

---

## Example: smallest request

```json
{
  "loadId": "LOAD-12345",
  "amount": 2500.00,
  "carrier": { "mcNumber": "123456" }
}
```

You can use `"carrier": { "dotNumber": "987654" }` instead if you only have a DOT number.

## Example: testing in sandbox with carrier info

```json
{
  "loadId": "LOAD-12345",
  "amount": 2500.00,
  "useSandbox": true,
  "notes": "Bid from board",
  "metadata": { "transportationMode": "Van" },
  "carrier": {
    "mcNumber": "123456",
    "dotNumber": "987654"
  }
}
```

---

## When it works

You should get **HTTP 201** and a small JSON body:

```json
{ "id": "…" }
```

The **`id`** is the new Salesforce carrier quote record. Keep it if you need to reference or update that quote later.

---

## When something goes wrong

Errors return JSON with a short **`code`** (stable, good for logging or scripts) and a **`message`** you can read or show to someone troubleshooting.

**Something wrong with the request (your side)**  
- **400** — Bad or missing JSON, missing `loadId` or `amount`, missing **`carrier`** or both **`mcNumber`** and **`dotNumber`** empty, invalid **`source.sourceType`** (must be one of the allowed picklist values or omitted/empty), invalid **`metadata.transportationMode`** (must match a **`rtms__Mode__c.Name`** or be omitted/empty), or an unsupported body encoding.  
- **405** — You didn’t use POST.

**Something wrong with TMS data (often fixable by correcting ids or setup)**  
- **404 — load not found** — No load with that **Name** in the org you targeted (check spelling and sandbox vs prod).  
- **404 — no carrier account** — MC/DOT and fallback logic didn’t resolve an account.  
- **404 — no carrier service** — No matching enabled carrier service for the profile and mode.

**Server or Salesforce issues**  
- **500** — Configuration problem, Salesforce client startup failure, query failure, or Salesforce rejected the create. The **`message`** usually hints at the next step (fix config, check permissions, validation rules, etc.).

Calling the API twice with the same payload **can create two quotes** unless you build your own idempotency (for example dedupe on your side).

### Typical error `code` values

| HTTP | `code` | Meaning |
|------|--------|---------|
| 400 | `INVALID_JSON` | Body is not valid JSON. |
| 400 | `INVALID_REQUEST` | Unsupported encoding (for example base64-wrapped body). |
| 400 | `VALIDATION_ERROR` | Missing or invalid fields per rules above. |
| 405 | `METHOD_NOT_ALLOWED` | Not POST. |
| 404 | `LOAD_NOT_FOUND` | No matching load **Name**. |
| 404 | `NO_CARRIER_ACCOUNT` | No account from MC/DOT/fallback. |
| 404 | `NO_CARRIER_SERVICE` | No matching carrier service. |
| 500 | `CONFIG_ERROR` | Server misconfiguration. |
| 500 | `SALESFORCE_CLIENT_ERROR` | Could not initialize Salesforce client. |
| 500 | `QUERY_ERROR` | SOQL or transport error during lookup. |
| 500 | `CREATE_FAILED` | Salesforce rejected the insert. |
