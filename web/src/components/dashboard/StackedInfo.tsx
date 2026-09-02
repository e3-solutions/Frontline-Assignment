import { ReactNode } from "react";

type StackedInfoProps = {
   label: string;
   value: ReactNode;
   valueClassName?: string;
};

export function StackedInfo({ label, value, valueClassName }: StackedInfoProps) {
   return (
      <div className="flex flex-col gap-1">
         <span className="text-xs uppercase tracking-wide text-slate-500">{label}</span>
         <span className={valueClassName ?? "text-sm text-slate-700"}>{value}</span>
      </div>
   );
}
