"use client";

type AgentPhoneProps = {
   variant?: "light" | "dark";
   className?: string;
};

export function AgentPhone({ variant = "light", className = "" }: AgentPhoneProps) {
   const agentPhone = process.env.NEXT_PUBLIC_AGENT_PHONE_NUMBER;

   if (!agentPhone) return null;

   const styles = {
      light: {
         label: "text-slate-500",
         phone: "text-slate-700 hover:text-slate-900",
      },
      dark: {
         label: "text-slate-400",
         phone: "text-slate-300 hover:text-white",
      },
   };

   const currentStyle = styles[variant];

   return (
      <div className={`flex items-center gap-2 text-sm ${className}`}>
         <span className={currentStyle.label}>Agent:</span>
         <a
            href={`tel:${agentPhone}`}
            className={`font-mono transition-colors ${currentStyle.phone}`}
         >
            {agentPhone}
         </a>
      </div>
   );
}
