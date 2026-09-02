import type { CallRecord, EmailRecord, LoadNegotiation, LoadRecord } from "@/src/types/dashboard";

export type NegotiationAnalytics = {
   successRate: {
      agreements: number;
      noAgreements: number;
      totalCalls: number;
      totalEmails: number;
      totalAttempts: number;
      rate: number; // percentage
   };
   pricing: {
      avgAgreedPrice: number;
      targetPrice: number;
      variance: number; // percentage vs target
      varanceAmount: number; // dollar amount vs target
   };
   timing: {
      fastestDeal: number; // seconds
      slowestDeal: number; // seconds
      averageDeal: number; // seconds
      fastestDealId?: string;
      slowestDealId?: string;
   };
   chartData: {
      date: string;
      price: number;
      target: number;
      timestamp: number;
   }[];
};

/**
 * Calculate comprehensive analytics for a load
 */
export function calculateLoadAnalytics(
   load: LoadRecord,
   calls: CallRecord[],
   emails?: EmailRecord[]
): NegotiationAnalytics | null {
   const { negotiations, data } = load;
   const targetPrice = data?.pricing?.target;

   // Filter calls and emails for this specific load
   const loadCalls = calls.filter((call) => call.loadId === load.loadId);
   const loadEmails = (emails ?? []).filter((e) => e.loadId === load.loadId);

   // The negotiations table already contains BOTH call-based and email-based
   // negotiation rows (email ones have callId=null). Do NOT add email
   // negotiations separately — that would double-count them.
   const agreements = negotiations.filter(
      (n) => !n.aboveMax && n.agreedPrice != null && n.agreedPrice > 0
   ).length;

   if (!targetPrice || (negotiations.length === 0 && loadCalls.length === 0 && loadEmails.length === 0)) {
      return null;
   }

   // Total attempts = calls + email threads
   const totalCalls = loadCalls.length;
   const totalEmails = loadEmails.length;
   const totalAttempts = totalCalls + totalEmails;
   const noAgreements = totalAttempts - agreements;

   const successRate = totalAttempts > 0 ? (agreements / totalAttempts) * 100 : 0;

   // Pricing — all agreed prices are already in negotiations (call + email)
   const prices = negotiations
      .map((n) => n.agreedPrice)
      .filter((price): price is number => typeof price === "number" && price > 0);

   const avgAgreedPrice =
      prices.length > 0 ? prices.reduce((sum, price) => sum + price, 0) / prices.length : 0;

   // Calculate variance: Negative = GOOD (paying less), Positive = BAD (paying more)
   // For brokers: Lower carrier rates = Higher profit
   const variance = ((avgAgreedPrice - targetPrice) / targetPrice) * 100;
   const varanceAmount = avgAgreedPrice - targetPrice;

   // Calculate timing metrics
   const dealTimes = negotiations
      .map((negotiation) => {
         // Skip if no call ID linked
         if (!negotiation.callId) {
            return null;
         }

         // Find the call that led to this negotiation
         const relatedCall = loadCalls.find(
            (call) => call.id === negotiation.callId && call.endReason === "agreement"
         );

         if (!relatedCall || !relatedCall.initiatedAt) {
            return null;
         }

         const callStart = new Date(relatedCall.initiatedAt).getTime();
         const negotiationEnd = new Date(negotiation.createdAt).getTime();
         const duration = (negotiationEnd - callStart) / 1000; // seconds

         return {
            duration,
            negotiationId: negotiation.id,
         };
      })
      .filter(
         (t): t is { duration: number; negotiationId: string } => t !== null && t.duration >= 0
      );

   const fastestDeal = dealTimes.length > 0 ? Math.min(...dealTimes.map((t) => t.duration)) : 0;
   const slowestDeal = dealTimes.length > 0 ? Math.max(...dealTimes.map((t) => t.duration)) : 0;
   const averageDeal =
      dealTimes.length > 0
         ? dealTimes.reduce((sum, t) => sum + t.duration, 0) / dealTimes.length
         : 0;

   const fastestDealId = dealTimes.find((t) => t.duration === fastestDeal)?.negotiationId;
   const slowestDealId = dealTimes.find((t) => t.duration === slowestDeal)?.negotiationId;

   // Prepare chart data - all negotiations are successes
   const chartData = negotiations
      .filter((n) => n.agreedPrice && n.agreedPrice > 0) // Only show negotiations with valid prices
      .map((negotiation) => ({
         date: new Date(negotiation.createdAt).toLocaleString("en-US", {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
         }),
         price: negotiation.agreedPrice || 0,
         target: targetPrice,
         timestamp: new Date(negotiation.createdAt).getTime(),
      }))
      .sort((a, b) => a.timestamp - b.timestamp);

   return {
      successRate: {
         agreements,
         noAgreements,
         totalCalls,
         totalEmails,
         totalAttempts,
         rate: Math.round(successRate * 10) / 10,
      },
      pricing: {
         avgAgreedPrice: Math.round(avgAgreedPrice * 100) / 100,
         targetPrice,
         variance: Math.round(variance * 10) / 10,
         varanceAmount: Math.round(varanceAmount * 100) / 100,
      },
      timing: {
         fastestDeal: Math.round(fastestDeal),
         slowestDeal: Math.round(slowestDeal),
         averageDeal: Math.round(averageDeal),
         fastestDealId,
         slowestDealId,
      },
      chartData,
   };
}

/**
 * Format time duration in human-readable format
 */
export function formatDuration(seconds: number): string {
   if (seconds < 60) {
      return `${seconds}s`;
   }
   const minutes = Math.floor(seconds / 60);
   const remainingSeconds = seconds % 60;
   if (minutes < 60) {
      return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
   }
   const hours = Math.floor(minutes / 60);
   const remainingMinutes = minutes % 60;
   return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}

/**
 * Format percentage with sign
 */
export function formatPercentage(value: number, includeSign: boolean = true): string {
   const sign = includeSign && value > 0 ? "+" : "";
   return `${sign}${value.toFixed(1)}%`;
}
