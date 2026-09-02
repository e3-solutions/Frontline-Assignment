type InfoTileProps = {
   label: string;
   value: string;
   highlight?: boolean;
};

export function InfoTile({ label, value, highlight = false }: InfoTileProps) {
   const containerClass = highlight
      ? "border-emerald-200 bg-emerald-50"
      : "border-slate-200 bg-slate-50";
   const valueClass = highlight ? "text-emerald-700" : "text-slate-900";

   return (
      <div
         className={`flex h-full flex-col justify-between rounded-lg border ${containerClass} p-3`}
      >
         <p className="text-xs uppercase tracking-wide text-slate-500 leading-tight">{label}</p>
         <p className={`text-sm font-medium ${valueClass}`}>{value}</p>
      </div>
   );
}
