"use client";

import { createBrowserClient } from "@supabase/ssr";

declare global {
   interface Window {
      __ENV__?: {
         SUPABASE_URL?: string;
         SUPABASE_ANON_KEY?: string;
      };
   }
}

// Read runtime env injected by `app/layout.tsx` via an inline <script> in
// <head>, so Railway's SUPABASE_URL/SUPABASE_ANON_KEY take effect without
// rebuilding the bundle. Falls back to the build-time-baked NEXT_PUBLIC_*
// for local dev or the brief window before the inline script runs (e.g., if
// imported during pre-render — though "use client" should prevent that).

// Track whether we've already logged for this page load — log once, not on
// every createSupabaseBrowserClient call (the function is invoked from many
// React components and would spam the console).
let hasLoggedSource = false;

function logSourceOnce(supabaseUrl: string, sourceWasRuntime: boolean): void {
   if (hasLoggedSource || typeof window === "undefined") return;
   hasLoggedSource = true;
   const source = sourceWasRuntime
      ? "runtime (window.__ENV__)"
      : "build-time fallback (NEXT_PUBLIC_SUPABASE_URL)";
   // eslint-disable-next-line no-console
   console.info(
      `[supabase] Browser client → ${supabaseUrl} (source: ${source})`,
   );
   if (!sourceWasRuntime) {
      // eslint-disable-next-line no-console
      console.warn(
         "[supabase] Using build-time fallback for SUPABASE_URL — runtime " +
            "injection via window.__ENV__ failed. If you set SUPABASE_URL in " +
            "Railway, verify the inline <script> in app/layout.tsx is reaching " +
            "the browser (check raw HTML for `window.__ENV__`).",
      );
   }
}

export const createSupabaseBrowserClient = () => {
   const fromWindow =
      typeof window !== "undefined" ? window.__ENV__?.SUPABASE_URL : undefined;
   const supabaseUrl = fromWindow || process.env.NEXT_PUBLIC_SUPABASE_URL;
   const supabaseAnonKey =
      (typeof window !== "undefined"
         ? window.__ENV__?.SUPABASE_ANON_KEY
         : undefined) || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

   if (!supabaseUrl) {
      throw new Error(
         "Supabase URL is not set (window.__ENV__.SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL)",
      );
   }
   if (!supabaseAnonKey) {
      throw new Error(
         "Supabase anon key is not set (window.__ENV__.SUPABASE_ANON_KEY or NEXT_PUBLIC_SUPABASE_ANON_KEY)",
      );
   }

   logSourceOnce(supabaseUrl, Boolean(fromWindow));

   return createBrowserClient(supabaseUrl, supabaseAnonKey);
};
