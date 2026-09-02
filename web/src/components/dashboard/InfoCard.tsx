import { ReactNode } from "react";

type InfoCardProps = {
   label: string;
   value: ReactNode;
   icon?: ReactNode;
   fullWidth?: boolean;
};

export function InfoCard({ label, value, icon, fullWidth = false }: InfoCardProps) {
   return (
      <div
         className={`rounded-lg border border-slate-200 bg-slate-50 p-4 ${
            fullWidth ? "md:col-span-2" : ""
         }`}
      >
         <p className="text-xs uppercase tracking-wide text-slate-500 mb-2">{label}</p>
         <div className="flex items-center gap-2 text-sm text-slate-700">
            {icon}
            <span className={fullWidth ? "leading-relaxed" : ""}>{value}</span>
         </div>
      </div>
   );
}
