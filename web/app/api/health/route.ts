// Diagnostic endpoint that reports which Supabase project the server thinks
// it is connected to. Useful in prod for confirming Railway's runtime env
// took effect after a deploy without needing to log in or read SSR HTML.
//
// SECURITY: only the URL and the env source are exposed — never the anon key
// or service-role key. The Supabase URL (project ref) is already public on
// every login network request, so leaking it here is no worse than baseline.

import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
   const runtimeUrl = process.env.SUPABASE_URL;
   const buildtimeUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
   const resolved = runtimeUrl || buildtimeUrl;

   const projectRef = resolved
      ? resolved.match(/^https?:\/\/([a-z0-9]+)\.supabase\./i)?.[1] ?? null
      : null;

   return NextResponse.json({
      ok: Boolean(resolved),
      supabase: {
         url: resolved ?? null,
         projectRef,
         source: runtimeUrl
            ? "runtime (Railway SUPABASE_URL)"
            : buildtimeUrl
              ? "build-time fallback (NEXT_PUBLIC_SUPABASE_URL)"
              : "unset",
      },
      runtimeEnvHasServiceRoleKey: Boolean(process.env.SUPABASE_SERVICE_ROLE_KEY),
      // If this is true and `source` is build-time, you have split-brain risk:
      // server/admin call paths that pair URL+service-role-key may target
      // different projects than the client's auth cookies.
      buildtimeAndRuntimeUrlMatch:
         Boolean(runtimeUrl) && runtimeUrl === buildtimeUrl,
   });
}
