import { ReactNode } from "react";

type SectionTitleProps = {
   title: string;
   subtitle: string;
   action?: ReactNode;
};

export function SectionTitle({ title, subtitle, action }: SectionTitleProps) {
   return (
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
         <div className="flex flex-col gap-1">
            <h2 className="text-xl font-semibold text-slate-900">{title}</h2>
            <p className="text-sm text-slate-500">{subtitle}</p>
         </div>
         {action ? <div className="shrink-0">{action}</div> : null}
      </div>
   );
}
