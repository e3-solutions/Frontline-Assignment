type MetricCardProps = {
   label: string;
   value: string | number;
   trend?: string;
   trendUp?: boolean;
   icon?: string;
   description?: string;
};

export function MetricCard({ label, value, trend, trendUp, icon, description }: MetricCardProps) {
   return (
      <div className="rounded-lg border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface)] p-4">
         <div className="flex items-start justify-between mb-2">
            <p className="text-xs uppercase tracking-wide text-[color:var(--e3-text-soft)] e3-font-mono">{label}</p>
            {icon && <span className="text-lg">{icon}</span>}
         </div>
         <div className="space-y-1">
            <p className="text-2xl font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">{value}</p>
            {trend && (
               <p
                  className={`text-xs font-medium ${
                     trendUp === true
                        ? "text-[color:var(--e3-chip-success-text)]"
                        : trendUp === false
                          ? "text-[color:var(--e3-chip-rose-text)]"
                          : "text-[color:var(--e3-text-soft)]"
                  }`}
               >
                  {trend}
               </p>
            )}
            {description && <p className="text-xs text-[color:var(--e3-text-muted)] e3-font-body">{description}</p>}
         </div>
      </div>
   );
}
