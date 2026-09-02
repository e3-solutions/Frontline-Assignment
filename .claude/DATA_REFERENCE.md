# Database Schema & Data Flow Reference

> **Historical schema reference:** The schema and query examples below predate the current load catalog. Use [the current load/stops contract](../docs/KCH_SUPABASE_SCHEMA.md) for application queries and [Database setup](../docs/DATABASE_SETUP.md) for initialization and sample data. The current `loads` table uses `load_number` and separate `stops`; it does not have the historical `id`, `org_id`, or `data` columns shown below.

## Quick Schema Overview

```sql
organizations
├── id (UUID, PK)
└── name

loads
├── id (UUID, PK)
├── load_id (TEXT) -- Human-readable like "7123"
├── org_id (UUID, FK → organizations)
└── data (JSONB) -- All load details

calls
├── id (UUID, PK)
├── load_id (UUID, FK → loads)
├── negotiation_result (UUID, FK → negotiations) -- NULL if failed
├── end_reason (ENUM) -- 'agreement', 'no_agreement', 'abrupt', 'error', 'load_not_found'
├── result (JSONB) -- transcription, notes, etc.
├── initiated_at (TIMESTAMPTZ)
└── ended_at (TIMESTAMPTZ)

negotiations
├── id (UUID, PK)
├── load_id (UUID, FK → loads)
├── call_id (UUID, FK → calls)
├── agreed_price (NUMERIC)
└── created_at (TIMESTAMPTZ)
```

## Load Data Structure (JSONB)

```typescript
data: {
  origin: "Los Angeles, CA",
  destination: "New York, NY",
  equipment: "Dry Van",
  weight: "40,000 lbs",
  pickupDate: "2025-11-15",
  dropoffDate: "2025-11-18",

  pricing: {
    initial: 2000,    // Opening bid to carrier
    target: 2500,     // Goal (CONFIDENTIAL)
    ceiling: 2800     // Max (NEVER EXCEED)
  },

  pushbackLevel: 7,   // 1-10 carrier resistance
  broker: "Acme Logistics",
  customer: "Widget Corp"
}
```

## TypeScript Types Reference

```typescript
// Load with aggregated data
type LoadRecord = {
	id: string; // UUID
	loadId: string; // "7123"
	orgId: string; // UUID
	createdAt: string; // ISO timestamp
	updatedAt: string; // ISO timestamp
	data?: LoadFormData; // See above
	callCount: number; // Total calls for this load
	negotiations: LoadNegotiation[]; // All successful negotiations
};

// Successful negotiation
type LoadNegotiation = {
	id: string; // UUID
	loadId: string; // Load UUID
	callId?: string; // Call UUID (if linked)
	createdAt: string; // When agreement reached
	agreedPrice?: number; // Final negotiated rate
	status: "success"; // Always "success" (by definition)
	notes?: string; // Optional notes
};

// Call record
type CallRecord = {
	id: string; // UUID
	loadId: string; // Load's human-readable ID (e.g., "7123")
	dailyCallId: string; // Daily.co call ID
	negotiationResult?: string; // Negotiation UUID if successful
	callerNumber: string;
	callerCountryCode: string;
	initiatedAt: string;
	endedAt?: string;
	endReason?: CallOutcome; // How call ended
	result: CallResult; // Additional data
};

type CallOutcome =
	| "agreement" // Success - negotiation completed
	| "no_agreement" // Failed - couldn't agree on rate
	| "abrupt" // Call ended unexpectedly
	| "error" // Technical issue
	| "load_not_found"; // Couldn't find the load
```

## Data Relationships

### One Load → Many Calls

```
Load "7123"
├── Call 1 (ended: agreement) → Negotiation 1 ($2,400)
├── Call 2 (ended: no_agreement) → NULL
├── Call 3 (ended: agreement) → Negotiation 2 ($2,500)
└── Call 4 (ended: abrupt) → NULL
```

### Success Determination

**A call is SUCCESSFUL if:**

- `calls.negotiation_result` is NOT NULL
- `calls.end_reason` is 'agreement'
- A row exists in `negotiations` table

**A call is UNSUCCESSFUL if:**

- `calls.negotiation_result` is NULL
- `calls.end_reason` is NOT 'agreement'
- No corresponding row in `negotiations` table

## Data Flow Examples

### Successful Negotiation Flow

```
1. Carrier calls
   ↓
2. AI: get_load_context("7123")
   ↓ Returns load data from DB
3. AI negotiates, reaches agreement at $2,400
   ↓
4. AI: record_agreement(2400, "7123", call_id)
   ↓ Creates row in negotiations table
   ↓ Links call → negotiation
5. AI: end_call("agreement")
   ↓ Updates call.end_reason

Result:
- 1 new row in negotiations
- call.negotiation_result = <negotiation_id>
- call.end_reason = 'agreement'
```

### Failed Negotiation Flow

```
1. Carrier calls
   ↓
2. AI: get_load_context("7123")
   ↓ Returns load data from DB
3. AI negotiates, can't reach agreement
   ↓
4. AI: end_call("no_agreement")
   ↓ Updates call.end_reason

Result:
- NO row in negotiations
- call.negotiation_result = NULL
- call.end_reason = 'no_agreement'
```

## Analytics Calculations

### Success Rate

```typescript
const totalCalls = calls.filter((c) => c.loadId === load.loadId).length;
const agreements = negotiations.length; // Every row = success
const successRate = (agreements / totalCalls) * 100;
```

### Variance (Performance Metric)

```typescript
const prices = negotiations.map((n) => n.agreedPrice);
const avgAgreedPrice = sum(prices) / prices.length;
const targetPrice = load.data.pricing.target;

// CRITICAL: Negative variance = GOOD (paying less)
const variance = ((avgAgreedPrice - targetPrice) / targetPrice) * 100;

// Example:
// Target: $2,500, Avg: $2,000
// Variance: (2000 - 2500) / 2500 = -20% ✅ EXCELLENT!
```

### Deal Time

```typescript
const dealTime = negotiations.map((neg) => {
	const call = calls.find((c) => c.id === neg.callId);
	const startTime = new Date(call.initiatedAt).getTime();
	const endTime = new Date(neg.createdAt).getTime();
	return (endTime - startTime) / 1000; // seconds
});
```

## Common Query Patterns

### Get all data for a load

```typescript
// Load with negotiations
const load = await fetchLoadsWithDetails();

// Related calls
const calls = await fetchCallsWithDetails();
const loadCalls = calls.filter((c) => c.loadId === load.loadId);

// Success count
const successCount = load.negotiations.length;
const totalCallCount = loadCalls.length;
```

### Check if call was successful

```typescript
const isSuccessful = (call: CallRecord) => {
	return call.negotiationResult !== undefined && call.endReason === "agreement";
};
```

### Get negotiation for a call

```typescript
const negotiation = load.negotiations.find((n) => n.callId === call.id);
```

## Important Notes for AI Assistants

1. **Never assume array indices match** - Always find by key/ID
2. **negotiations.length = success count** - It's pre-filtered
3. **Lower agreed prices = better performance** - Don't invert this logic
4. **calls.loadId is a STRING** (like "7123"), not the UUID
5. **Every negotiation row is a success** - No need to filter by status
6. **Null negotiation_result = failed call** - Simple to check

## Testing Data Scenarios

### Scenario A: High Success, Low Rates (EXCELLENT)

```
Load 7123:
- Target: $2,500
- 10 calls total
- 8 negotiations (80% success)
- Avg agreed: $2,200 (-12% variance)
→ AI is performing EXCELLENTLY
```

### Scenario B: Low Success, High Rates (POOR)

```
Load 7123:
- Target: $2,500
- 10 calls total
- 4 negotiations (40% success)
- Avg agreed: $2,800 (+12% variance)
→ AI needs improvement
```

### Scenario C: Perfect Performance (IDEAL)

```
Load 7123:
- Target: $2,500
- 10 calls total
- 9 negotiations (90% success)
- Avg agreed: $2,100 (-16% variance)
→ AI is exceeding expectations
```
