import type { CallRecord, EmailRecord, LoadRecord } from "@/src/types/dashboard";
import { calculateLoadAnalytics, formatDuration, formatPercentage } from "@/src/services/analytics";
import { formatCurrency } from "@/src/utils/format";
import { cx } from "@e3-solutions/ui";

type LoadAnalyticsSectionProps = {
   load: LoadRecord;
   calls: CallRecord[];
   emails?: EmailRecord[];
};

function Stat({
   label,
   value,
   sub,
   tone,
}: {
   label: string;
   value: string;
   sub?: string;
   tone?: "success" | "rose" | "amber" | "muted";
}) {
   const valueColor =
      tone === "success"
         ? "text-[color:var(--e3-chip-success-text)]"
         : tone === "rose"
           ? "text-[color:var(--e3-chip-rose-text)]"
           : tone === "amber"
             ? "text-[color:var(--e3-chip-amber-text)]"
             : "text-[color:var(--e3-text-strong)]";

   return (
      <div className="text-center">
         <p className="text-[11px] uppercase tracking-[0.12em] text-[color:var(--e3-text-soft)] e3-font-mono">
            {label}
         </p>
         <p className={cx("mt-1 text-xl font-bold e3-font-heading", valueColor)}>{value}</p>
         {sub && (
            <p className="mt-0.5 text-xs text-[color:var(--e3-text-muted)] e3-font-body">{sub}</p>
         )}
      </div>
   );
}

export function LoadAnalyticsSection({ load, calls, emails }: LoadAnalyticsSectionProps) {
   const analytics = calculateLoadAnalytics(load, calls, emails);

   if (!analytics) {
      return null;
   }

   const { successRate, pricing, timing } = analytics;
   const varianceTone: "success" | "rose" | "amber" =
      pricing.variance < 0 ? "success" : pricing.variance < 15 ? "amber" : "rose";

   return (
      <div className="space-y-4 border-b border-[color:var(--e3-divider)] pb-5">
         <div className="flex items-center justify-between">
            <h3 className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--e3-text-soft)] e3-font-mono">
               Analytics
            </h3>
            <span className="text-[10px] text-[color:var(--e3-text-muted)] e3-font-mono">
               {successRate.agreements} agreed / {successRate.totalAttempts} attempts
            </span>
         </div>

         {/* Stats row */}
         <div className="grid grid-cols-4 gap-2 rounded-xl border border-[color:var(--e3-border-subtle)] bg-[color:var(--e3-surface-soft)] px-3 py-3">
            <Stat
               label="Success"
               value={`${successRate.rate}%`}
               sub={`${successRate.agreements}/${successRate.totalAttempts}`}
               tone={successRate.rate >= 50 ? "success" : successRate.rate > 0 ? "amber" : "muted"}
            />
            <Stat
               label="vs Target"
               value={formatPercentage(pricing.variance)}
               sub={formatCurrency(Math.abs(pricing.varanceAmount))}
               tone={varianceTone}
            />
            <Stat
               label="Avg Time"
               value={timing.averageDeal > 0 ? formatDuration(timing.averageDeal) : "—"}
               sub={timing.fastestDeal > 0 ? `${formatDuration(timing.fastestDeal)} fastest` : undefined}
            />
            <Stat
               label="Avg Price"
               value={formatCurrency(pricing.avgAgreedPrice)}
               sub={`Target ${formatCurrency(pricing.targetPrice)}`}
            />
         </div>

      </div>
   );
}
