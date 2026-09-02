"use client";

import { useMemo, useState } from "react";

import {
   MailIcon,
   MetricCard,
   PhoneIcon,
   TruckIcon,
   formatCurrency,
} from "@e3-solutions/ui";

import { CallsTable } from "@/src/components/dashboard/CallCard";
import { EmailsTable } from "@/src/components/dashboard/EmailCard";
import { LoadsTable } from "@/src/components/dashboard/LoadCard";
import type { CallRecord, EmailRecord, LoadRecord } from "@/src/types/dashboard";

type DashboardHomeProps = {
   userName: string;
   loads: LoadRecord[];
   calls: CallRecord[];
   emails: EmailRecord[];
   onNavigate: (view: string) => void;
   onCreateLoad: () => void;
   onOpenLoadDetails: (load: LoadRecord) => void;
};

function getGreeting(): string {
   const hour = new Date().getHours();
   if (hour < 12) return "Good morning";
   if (hour < 17) return "Good afternoon";
   return "Good evening";
}

function getFirstName(fullName: string): string {
   return fullName.split(" ")[0] || fullName;
}

type DerivedMetrics = {
   totalNegotiations: number;
   successfulDeals: number;
   aboveMaxDeals: number;
   successRate: number;
   avgSavings: number;
   loadsWithoutNegotiations: number;
   recentAgreements24h: number;
   voiceAgreements: number;
   activeEmailThreads: number;
   endedEmailThreads: number;
   outcomeDistribution: Record<string, number>;
   recentNegotiations: {
      loadId: string;
      price: number;
      status: "success" | "violet" | "amber" | "rose";
      statusLabel: string;
      date: string;
   }[];
};

function computeMetrics(loads: LoadRecord[], calls: CallRecord[], emails: EmailRecord[]): DerivedMetrics {
   // The negotiations table already contains BOTH call and email negotiation rows.
   // Email-originated rows have callId=null. Do NOT double-count by also
   // adding from email_thread.negotiations — those are the same rows.
   const allNegotiations = loads.flatMap((l) => l.negotiations);
   const successfulDeals = allNegotiations.filter((n) => !n.aboveMax && n.agreedPrice && n.agreedPrice > 0).length;
   const aboveMaxDeals = allNegotiations.filter((n) => n.aboveMax).length;

   // Total attempts = calls + ended email threads
   const endedEmails = emails.filter((e) => e.ended || e.negotiation);
   const totalAttempts = calls.length + endedEmails.length;
   const totalNegotiations = totalAttempts > 0 ? totalAttempts : allNegotiations.length;
   const successRate = totalNegotiations > 0 ? (successfulDeals / totalNegotiations) * 100 : 0;

   // Savings — all from negotiations table (already includes call + email)
   const allSavings = loads.flatMap((load) => {
      const target = load.data?.pricing?.target;
      if (!target) return [];
      return load.negotiations
         .filter((n) => !n.aboveMax && n.agreedPrice && n.agreedPrice > 0)
         .map((n) => target - n.agreedPrice!);
   });
   const avgSavings = allSavings.length > 0 ? allSavings.reduce((a, b) => a + b, 0) / allSavings.length : 0;

   const loadsWithoutNegotiations = loads.filter((l) => l.negotiations.length === 0).length;

   const oneDayAgo = Date.now() - 24 * 60 * 60 * 1000;
   const recentAgreements24h = allNegotiations.filter(
      (n) => !n.aboveMax && n.agreedPrice && new Date(n.createdAt).getTime() > oneDayAgo
   ).length;

   const voiceAgreements = calls.filter(
      (c) => (c.endReason ?? c.result.outcome) === "agreement"
   ).length;

   const activeEmailThreads = emails.filter((e) => !e.ended).length;
   const endedEmailThreads = emails.filter((e) => e.ended).length;

   const outcomeDistribution: Record<string, number> = {};
   for (const call of calls) {
      const outcome = call.endReason ?? call.result.outcome;
      outcomeDistribution[outcome] = (outcomeDistribution[outcome] || 0) + 1;
   }

   const recentNegotiations = [...allNegotiations]
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      .slice(0, 5)
      .map((n) => {
         const isAboveMax = n.aboveMax;
         const isSuccess = !isAboveMax && n.agreedPrice && n.agreedPrice > 0;
         return {
            loadId: n.loadId,
            price: n.agreedPrice ?? 0,
            status: (isSuccess ? "success" : isAboveMax ? "violet" : "amber") as "success" | "violet" | "amber" | "rose",
            statusLabel: isSuccess ? "Agreed" : isAboveMax ? "Bid Placed" : "No Agreement",
            date: n.createdAt,
         };
      });

   return {
      totalNegotiations,
      successfulDeals,
      aboveMaxDeals,
      successRate,
      avgSavings,
      loadsWithoutNegotiations,
      recentAgreements24h,
      voiceAgreements,
      activeEmailThreads,
      endedEmailThreads,
      outcomeDistribution,
      recentNegotiations,
   };
}

const outcomeLabels: Record<string, string> = {
   agreement: "Agreed",
   bid_placed: "Bid Placed",
   no_agreement: "No Agreement",
   abrupt: "Abrupt",
   error: "Error",
   load_not_found: "Load Not Found",
   mc_not_found: "MC Not Found",
   call_transferred: "Transferred",
};

const outcomeColors: Record<string, string> = {
   agreement: "#10b981",
   bid_placed: "#8b5cf6",
   no_agreement: "#f59e0b",
   abrupt: "#f43f5e",
   error: "#f43f5e",
   load_not_found: "#38bdf8",
   mc_not_found: "#38bdf8",
   call_transferred: "#38bdf8",
};

export function DashboardHome({ userName, loads, calls, emails, onNavigate, onCreateLoad, onOpenLoadDetails }: DashboardHomeProps) {
   const m = useMemo(() => computeMetrics(loads, calls, emails), [loads, calls, emails]);
   const [expandedCallId, setExpandedCallId] = useState<string | null>(null);
   const [expandedLoadId, setExpandedLoadId] = useState<string | null>(null);

   return (
      <div className="space-y-8">
         {/* Header */}
         <header className="flex items-start justify-between">
            <div>
               <h1 className="text-3xl font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                  {getGreeting()}, {getFirstName(userName)}
               </h1>
               <p className="mt-1 text-sm text-[color:var(--e3-text-muted)] e3-font-body">
                  Here&apos;s how your negotiation agent is performing
               </p>
            </div>
            <button
               type="button"
               onClick={onCreateLoad}
               className="inline-flex h-10 items-center rounded-xl bg-[color:var(--e3-brand-accent)] px-5 text-sm font-semibold text-white transition-all hover:bg-[color:var(--e3-brand-deep)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--e3-brand-accent)] focus-visible:ring-offset-2 active:scale-[0.98] e3-font-heading"
            >
               Create Load
            </button>
         </header>

         {/* Key Metrics */}
         <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
            <MetricCard label="Total Loads" value={loads.length} />
            <MetricCard
               label="Negotiations"
               value={m.totalNegotiations}
               description={`${m.successfulDeals} successful`}
            />
            <MetricCard
               label="Success Rate"
               value={`${m.successRate.toFixed(0)}%`}
               trendUp={m.successRate >= 50 ? true : m.successRate > 0 ? false : undefined}
               trend={m.successRate >= 70 ? "Strong" : m.successRate >= 50 ? "Moderate" : m.totalNegotiations === 0 ? "" : "Needs attention"}
            />
            <MetricCard
               label="Avg Savings"
               value={m.avgSavings > 0 ? formatCurrency(m.avgSavings) : "$0"}
               description="vs target rate"
               trendUp={m.avgSavings > 0 ? true : undefined}
            />
            <MetricCard
               label="Agreements (24h)"
               value={m.recentAgreements24h}
               trendUp={m.recentAgreements24h > 0 ? true : undefined}
            />
            <MetricCard
               label="Above Max"
               value={m.aboveMaxDeals}
               description={m.aboveMaxDeals > 0 ? "needs follow-up" : ""}
               trendUp={m.aboveMaxDeals > 0 ? false : undefined}
            />
         </div>

         {/* ── Loads ── */}
         <section>
            <div className="mb-4 flex items-center justify-between">
               <h3 className="flex items-center gap-2 text-lg font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                  <TruckIcon className="h-5 w-5" /> Recent Loads
               </h3>
               <button
                  type="button"
                  onClick={() => onNavigate("loads")}
                  className="text-sm text-[color:var(--e3-brand-lavender)] transition-colors hover:text-[color:var(--e3-text-strong)] e3-font-body"
               >
                  View all loads →
               </button>
            </div>
            <LoadsTable
               loads={loads.slice(0, 5)}
               expandedLoadId={expandedLoadId}
               onExpandedLoadChange={setExpandedLoadId}
               onOpenLoadDetails={onOpenLoadDetails}
               emptyState={{ title: "No loads yet", description: "Create your first load to get started." }}
            />
         </section>

         {/* ── Calls ── */}
         <section>
            <div className="mb-4 flex items-center justify-between">
               <h3 className="flex items-center gap-2 text-lg font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                  <PhoneIcon className="h-5 w-5" /> Calls
               </h3>
               <button
                  type="button"
                  onClick={() => onNavigate("calls")}
                  className="text-sm text-[color:var(--e3-brand-lavender)] transition-colors hover:text-[color:var(--e3-text-strong)] e3-font-body"
               >
                  View all calls →
               </button>
            </div>
            {calls.length > 0 && Object.keys(m.outcomeDistribution).length > 0 && (
               <div className="mb-4 rounded-[22px] border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface)] px-6 py-4">
                  <div className="mb-3 flex h-3 w-full overflow-hidden rounded-full">
                     {Object.entries(m.outcomeDistribution)
                        .sort(([, a], [, b]) => b - a)
                        .map(([outcome, count]) => (
                           <div
                              key={outcome}
                              className="h-full transition-all"
                              style={{
                                 width: `${(count / calls.length) * 100}%`,
                                 backgroundColor: outcomeColors[outcome] || "#94a3b8",
                              }}
                              title={`${outcomeLabels[outcome] || outcome}: ${count}`}
                           />
                        ))}
                  </div>
                  <div className="flex flex-wrap gap-x-5 gap-y-1.5">
                     {Object.entries(m.outcomeDistribution)
                        .sort(([, a], [, b]) => b - a)
                        .map(([outcome, count]) => (
                           <div key={outcome} className="flex items-center gap-1.5">
                              <div className="h-2 w-2 rounded-full" style={{ backgroundColor: outcomeColors[outcome] || "#94a3b8" }} />
                              <span className="text-xs text-[color:var(--e3-text-muted)] e3-font-body">{outcomeLabels[outcome] || outcome}</span>
                              <span className="text-xs font-semibold text-[color:var(--e3-text-strong)] e3-font-mono">{count}</span>
                           </div>
                        ))}
                  </div>
               </div>
            )}
            <CallsTable
               calls={calls.slice(0, 5)}
               expandedCallId={expandedCallId}
               onExpandedCallChange={setExpandedCallId}
               sort="started_desc"
               onStartedSortToggle={() => {}}
               emptyState={{ title: "No calls yet", description: "Calls will appear here after negotiations begin." }}
            />
         </section>

         {/* ── Emails ── */}
         <section>
            <div className="mb-4 flex items-center justify-between">
               <h3 className="flex items-center gap-2 text-lg font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                  <MailIcon className="h-5 w-5" /> Email Threads
               </h3>
               <button
                  type="button"
                  onClick={() => onNavigate("emails")}
                  className="text-sm text-[color:var(--e3-brand-lavender)] transition-colors hover:text-[color:var(--e3-text-strong)] e3-font-body"
               >
                  View all emails →
               </button>
            </div>
            <EmailsTable
               emails={emails.slice(0, 5)}
               emptyState={{ title: "No email threads yet", description: "Email negotiations will appear here once threads are started." }}
            />
         </section>

      </div>
   );
}
