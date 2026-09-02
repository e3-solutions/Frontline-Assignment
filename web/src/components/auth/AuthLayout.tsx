"use client";

import type { ReactNode } from "react";
import { PageShell, ShellCard } from "@e3-solutions/ui";
import { ThemedLogo } from "@/src/components/ThemedLogo";

interface AuthLayoutProps {
   children: ReactNode;
   subtitle?: string;
}

export function AuthLayout({ children, subtitle }: AuthLayoutProps) {
   return (
      <PageShell className="flex items-center justify-center px-4 py-8 e3-font-body">
         <div className="mx-auto w-[42rem] max-w-[calc(100vw-2rem)]">
            <ShellCard className="w-full p-8 sm:p-10">
               <div className="mb-10 flex flex-col items-center text-center">
                  <ThemedLogo
                     width={309}
                     height={61}
                     priority
                     className="mb-5 h-auto max-w-[276px] object-contain"
                  />
                  <h1 className="e3-page-title text-3xl font-[family-name:var(--font-oxanium)]">Negotiation Center</h1>
                  {subtitle && <p className="e3-page-copy mt-2 text-sm">{subtitle}</p>}
               </div>

               <div className="min-h-[420px]">{children}</div>
            </ShellCard>
         </div>
      </PageShell>
   );
}
