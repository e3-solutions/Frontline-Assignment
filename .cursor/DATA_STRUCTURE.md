# Data Structure Overview

> **Historical schema reference:** The schema and query examples below predate the current load catalog. Use [the current load/stops contract](../docs/KCH_SUPABASE_SCHEMA.md) for application queries and [Database setup](../docs/DATABASE_SETUP.md) for initialization and sample data. The current `loads` table uses `load_number` and separate `stops`; it does not have the historical `id`, `org_id`, or `data` columns shown below.

## Core Entities

### 1. Organizations (`organizations` table)

- Each broker company using the system
- All loads belong to an organization

### 2. Loads (`loads` table)

```
id (UUID)              - Internal database ID
load_id (string)       - Human-readable ID (e.g., "7123")
org_id (UUID)          - Organization this load belongs to
data (JSONB)           - Load details including:
  ├─ origin          - Pickup location
  ├─ destination     - Delivery location
  ├─ pricing
  │  ├─ initial      - Opening offer to carrier
  │  ├─ target       - Ideal closing price (GOAL)
  │  └─ ceiling      - Maximum acceptable rate (NEVER EXCEED)
  ├─ pushbackLevel   - Expected carrier resistance (1-10)
  ├─ broker          - Broker name
  └─ customer        - Shipper/customer name
```

**Key: One load can have multiple calls and negotiations**

### 3. Calls (`calls` table)

```
id (UUID)                    - Unique call ID
load_id (UUID)               - Reference to loads table
negotiation_result (UUID)    - Reference to negotiations table (if successful)
end_reason (enum)            - How the call ended:
  ├─ 'agreement'           → Successful negotiation
  ├─ 'no_agreement'        → Tried but failed to agree
  ├─ 'abrupt'              → Call ended unexpectedly
  ├─ 'error'               → Technical issue
  └─ 'load_not_found'      → Couldn't find load
result (JSONB)               - Additional data:
  ├─ outcome             - Call outcome
  ├─ transcription       - Call transcript
  └─ notes               - Additional notes
initiated_at                 - When call started
ended_at                     - When call ended
```

**Key: If `negotiation_result` is NULL and `end_reason` is NOT 'agreement', the call was unsuccessful**

### 4. Negotiations (`negotiations` table)

```
id (UUID)           - Unique negotiation ID
load_id (UUID)      - Reference to loads table
call_id (UUID)      - Reference to calls table
agreed_price        - Final agreed rate
created_at          - When agreement was reached
```

**Key: Every row in negotiations = a SUCCESS. By definition, these are agreements.**

## Relationships

```
loads (1) ─┬─→ (many) calls
           └─→ (many) negotiations

calls (1) ──→ (0 or 1) negotiations
```

### Success vs Failure Logic

**SUCCESS = Row exists in `negotiations` table**

- Call will have `negotiation_result` pointing to the negotiation
- Call will have `end_reason = 'agreement'`

**FAILURE = Call exists WITHOUT linked negotiation**

- Call has `negotiation_result = NULL`
- Call has `end_reason` as:
  - `'no_agreement'` - Negotiation failed to reach agreement
  - `'abrupt'` - Call ended unexpectedly
  - `'error'` - Technical issue
  - `'load_not_found'` - Load couldn't be found

## Example Scenario

Load "7123" has:

- **15 calls total**

  - 10 calls with `end_reason = 'agreement'` (linked to negotiations)
  - 3 calls with `end_reason = 'no_agreement'` (no deal reached)
  - 2 calls with `end_reason = 'abrupt'` (carrier hung up)

- **10 negotiations** (one for each successful call)
  - Each has an `agreed_price`
  - Each represents a completed deal

**Success Rate = 10 negotiations / 15 calls = 66.7%**

## Function Call Flow (LLM Integration)

1. Carrier calls → AI answers
2. AI uses `get_load_context(load_id)` → Retrieves load data from Supabase
3. AI negotiates using pricing strategy
4. If agreement reached:
   - AI calls `record_agreement(agreed_price, load_id, call_id)`
   - Creates row in `negotiations` table
   - Links to `calls` table via `negotiation_result`
5. AI calls `end_call(reason)` → Updates call with `end_reason`

All data flows through LLM function calls to Supabase.
