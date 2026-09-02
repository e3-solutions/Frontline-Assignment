import type { Metadata } from "next";
import { Geist, Geist_Mono, Oxanium } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/src/contexts/AuthContext";
import { ThemeProvider } from "@/src/contexts/ThemeContext";

// Force dynamic rendering so `process.env.SUPABASE_URL` (a runtime-only var
// set in Railway) is read on every request instead of frozen at build time.
// Without this, Next.js may statically render the layout and bake stale env
// values into the injected `window.__ENV__` script below.
export const dynamic = "force-dynamic";

// Build the runtime env payload that gets shipped to the browser via an
// inline <script>. Server-side reads runtime env first (Railway), falls back
// to the build-time-baked NEXT_PUBLIC_* values for local dev. The browser-side
// Supabase client reads window.__ENV__ before falling back to its own
// build-time NEXT_PUBLIC_* — this means redeploying with a different Railway
// SUPABASE_URL re-points the browser without rebuilding the JS bundle.
function getRuntimePublicEnv() {
   return {
      SUPABASE_URL:
         process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
      SUPABASE_ANON_KEY:
         process.env.SUPABASE_ANON_KEY ??
         process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??
         "",
   };
}

// JSON.stringify can produce strings that break out of an inline <script>
// (e.g., a value containing `</script>`). Escape `<` to be safe.
function safeJson(value: unknown): string {
   return JSON.stringify(value).replace(/</g, "\\u003c");
}

const geistSans = Geist({
   variable: "--font-geist-sans",
   subsets: ["latin"],
});

const geistMono = Geist_Mono({
   variable: "--font-geist-mono",
   subsets: ["latin"],
});

const oxanium = Oxanium({
   variable: "--font-oxanium",
   subsets: ["latin"],
});

export const metadata: Metadata = {
   title: "Negotiation Agent",
   description: "AI-powered freight negotiation agent",
   icons: {
      icon: "/favicon.webp",
   },
};

export default function RootLayout({
   children,
}: Readonly<{
   children: React.ReactNode;
}>) {
   const runtimeEnv = getRuntimePublicEnv();

   return (
      <html lang="en" suppressHydrationWarning>
         <head>
            {/*
             * Runtime public env injection. Must execute BEFORE any bundle
             * script that imports `src/db/client.ts`, so the inline tag goes
             * first in <head>. Browser Supabase client reads window.__ENV__
             * at module-import time.
             */}
            <script
               dangerouslySetInnerHTML={{
                  __html: `window.__ENV__=${safeJson(runtimeEnv)};`,
               }}
            />
            <script
               dangerouslySetInnerHTML={{
                  __html: `try{var t=localStorage.getItem('e3-theme');if(t==='light'||t==='dark'){document.documentElement.dataset.theme=t;if(t==='light'){var l=document.querySelector('link[rel=\"icon\"]');if(l)l.href='/favicon-light.webp';}}}catch(e){if(typeof console!=='undefined')console.warn('Theme init error:',e)}`,
               }}
            />
         </head>
         <body className={`${geistSans.variable} ${geistMono.variable} ${oxanium.variable} antialiased`}>
            <AuthProvider>
               <ThemeProvider>
                  {children}
               </ThemeProvider>
            </AuthProvider>
         </body>
      </html>
   );
}
