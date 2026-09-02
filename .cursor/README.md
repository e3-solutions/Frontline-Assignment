# Freight Broker Negotiation AI - Business Context

## Business Model Overview

This software serves **freight brokers** who act as intermediaries between shippers (customers with goods to move) and carriers (trucking companies that move the goods).

### How Freight Brokers Make Money

```
Shipper pays broker:        $3,500
Broker pays carrier:       -$2,500  ← Our AI negotiates this DOWN
─────────────────────────────────
Broker's profit:            $1,000
```

**Key Principle: LOWER carrier rates = HIGHER broker profit**

### The Negotiation Challenge

When a carrier calls about a load, the broker must:

1. **Anchor low** - Start negotiations at the lowest acceptable rate
2. **Negotiate UP slowly** - Only increase rate when necessary ($25-100 increments)
3. **Stay below maximum** - Never exceed the max rate (would cause a loss)
4. **Maximize margin** - The lower the final agreed rate, the better

### Success Metrics

**EXCELLENT** ✅ - Agreed rate is BELOW target (more profit than expected)
**GOOD** ✓ - Agreed rate is AT target (expected profit margin)
**ACCEPTABLE** ⚠️ - Agreed rate is between target and max (reduced profit)
**UNACCEPTABLE** ❌ - Agreed rate is ABOVE max (would lose money)

### Rate Zones (from negotiation prompt)

Given a load with:

- Initial Offer: $2,000 (opening bid to carrier)
- Target Rate: $2,500 (ideal closing price - CONFIDENTIAL)
- Max Rate: $2,800 (ceiling - NEVER EXCEED)

**Zone 1: Below $2,500** → EXCELLENT deal, AI maximized profit
**Zone 2: $2,500-$2,800** → Acceptable, but could be better
**Zone 3: Above $2,800** → Reject, would lose money

### Our AI's Goal

The AI negotiation agent's success is measured by:

1. **Lowest possible agreed rate** (more profit for broker)
2. **High success rate** (closing deals without walking away)
3. **Fast deal time** (efficient negotiations)

**The AI is performing WELL when agreed rates are BELOW target.**
