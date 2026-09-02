const toneStyles = {
   default: {
      container: "border-slate-200 bg-slate-50",
      value: "text-slate-900",
   },
   emerald: {
      container: "border-emerald-200 bg-emerald-50",
      value: "text-emerald-700",
   },
   sky: {
      container: "border-sky-200 bg-sky-50",
      value: "text-sky-700",
   },
   violet: {
      container: "border-violet-200 bg-violet-50",
      value: "text-violet-700",
   },
} as const;

type StatPillTone = keyof typeof toneStyles;

type StatPillProps = {
   label: string;
   value: string;
   className?: string;
   tone?: Exclude<StatPillTone, "default">;
};

export function StatPill({ label, value, className, tone }: StatPillProps) {
   const styles = tone ? toneStyles[tone] : toneStyles.default;

   return (
      <div
         className={`flex items-center justify-between rounded-lg border px-4 py-3 text-sm ${
            styles.container
         } ${className ?? ""}`}
      >
         <span className="text-slate-600">{label}</span>
         <span className={`ml-2 font-semibold ${styles.value}`}>{value}</span>
      </div>
   );
}
