# Freight Broker Negotiation AI - Project Overview

## What This System Does

This is a **voice-based AI negotiation agent** for freight brokers. When a carrier calls about moving a load, the AI answers the phone and negotiates the rate on behalf of the broker.

## Business Model (Critical Understanding)

### The Freight Broker Role

Freight brokers are **intermediaries** who:

1. Get loads from shippers (customers who need goods moved)
2. Find carriers (trucking companies) to move those loads
3. Make profit on the spread between what they charge and what they pay

### The Profit Equation

```
Revenue:  Shipper pays broker $3,500
Cost:     Broker pays carrier $2,500  ← AI negotiates this DOWN
─────────────────────────────────────
Profit:   Broker keeps $1,000
```

**CRITICAL: Lower carrier rates = Higher broker profit**

### Why "Lower is Better"

The AI's job is to **minimize** what the broker pays to carriers, NOT maximize it:

- If AI negotiates carrier rate to $2,000 → Broker profit = $1,500 ✅ EXCELLENT
- If AI negotiates carrier rate to $2,500 → Broker profit = $1,000 ✓ GOOD (target)
- If AI negotiates carrier rate to $3,000 → Broker profit = $500 ⚠️ POOR
- If AI negotiates carrier rate to $3,600 → Broker profit = -$100 ❌ LOSS!

## Tech Stack

### Backend (Python)

- **Pipecat**: Voice AI framework for phone calls
- **Daily.co**: Real-time voice infrastructure
- **Supabase**: PostgreSQL database
- **LLM Function Calls**: AI retrieves/stores data via function calls

### Frontend (TypeScript/React)

- **Next.js 16** (App Router)
- **React 19**
- **Tailwind CSS 4**
- **Recharts**: Data visualization
- **Supabase Client**: Database queries

## How It Works

### Call Flow

1. **Carrier calls** about a load (e.g., Load #7123)
2. **AI answers** and asks for the load ID
3. **AI retrieves context** via `get_load_context(load_id)` function
4. **AI negotiates** using the freight broker strategy
5. **AI records agreement** via `record_agreement(price)` if successful
6. **AI ends call** via `end_call(reason)` function

### Negotiation Strategy (from `negotiation_prompt.py`)

The AI has three confidential price points:

- **Initial Offer**: $2,000 (opening bid to carrier)
- **Target Rate**: $2,500 (goal - keep this secret from carrier)
- **Max Rate**: $2,800 (ceiling - NEVER exceed)

The AI tries to close deals as **low as possible**, ideally below target.

## Key Terminology

- **Load**: A shipment that needs to be moved from A to B
- **Carrier**: Trucking company that moves the load
- **Shipper**: Customer who needs the load moved
- **Broker**: Intermediary (our client) who connects shippers and carriers
- **Rate**: Price paid to carrier for moving the load
- **Lane**: Route from origin to destination (e.g., LA to NYC)
- **Pushback Level**: Expected carrier resistance (1-10 scale)

## Success Metrics

From the broker's perspective:

### Excellent Performance ✅

- Agreed rates are **below target**
- Example: Target $2,500, Agreed $2,200 = -12% (GREAT!)

### Acceptable Performance ✓

- Agreed rates are **at or slightly above target**
- Example: Target $2,500, Agreed $2,600 = +4% (OK)

### Poor Performance ❌

- Agreed rates are **significantly above target**
- Example: Target $2,500, Agreed $3,000 = +20% (BAD!)

## When Working on This Project

### Remember:

1. **Lower negotiated rates = Better AI performance** (more broker profit)
2. **Negative variance is GOOD** (paying less than target)
3. **Positive variance is BAD** (paying more than target)
4. **Green metrics should celebrate LOW rates**, not high ones
5. **The AI is negotiating DOWN**, not up

### Analytics Logic:

- Chart shows: Green line (actual rates) vs Blue dashed line (target)
- **Good**: Green line BELOW blue line (paying less than target)
- **Bad**: Green line ABOVE blue line (paying more than target)

### Database:

- `negotiations` table = only successful deals
- `calls` table = all call attempts (success + failures)
- Every negotiation row is a success by definition
- Failed calls have no linked negotiation

## Common Pitfalls to Avoid

❌ **DON'T**: Think higher rates mean better performance
✅ **DO**: Remember brokers want to pay carriers LESS

❌ **DON'T**: Show green/positive indicators for high rates
✅ **DO**: Show green/positive indicators for LOW rates (below target)

❌ **DON'T**: Celebrate variance above target
✅ **DO**: Celebrate variance BELOW target

❌ **DON'T**: Assume all calls in database are successful
✅ **DO**: Remember only calls with linked negotiations are successful

## File Structure Highlights

```
negotiation/
├── voice-agent/             # Voice AI backend (Python)
│   ├── bot.py              # Main bot logic
│   ├── negotiation_prompt.py  # AI negotiation strategy
│   └── db_operations.py    # Supabase operations
│
└── web/                    # Dashboard frontend (Next.js)
    ├── app/                # Next.js app router
    ├── src/
    │   ├── components/
    │   │   ├── dashboard/  # Main UI components
    │   │   └── analytics/  # Analytics visualizations
    │   ├── services/
    │   │   ├── analytics.ts   # Analytics calculations
    │   │   └── dashboard.ts   # Data fetching
    │   └── types/
    │       └── dashboard.ts   # TypeScript types
    │
    └── supabase/
        └── migrations/     # Database schema
```

## Quick Reference

**When you see:**

- `-19.5%` variance → EXCELLENT (paying 19.5% less than target)
- `+8.2%` variance → POOR (paying 8.2% more than target)
- Green line below blue → AI is doing great!
- Green line above blue → AI needs improvement

**Remember the mantra:**

> "In freight brokerage, lower carrier rates = higher broker profits = better AI performance"
