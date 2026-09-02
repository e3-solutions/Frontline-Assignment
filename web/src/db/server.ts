import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";

// Server-side Supabase reads runtime env first (so Railway's
// SUPABASE_URL / SUPABASE_ANON_KEY are the source of truth at runtime),
// falling back to the build-time-baked NEXT_PUBLIC_* values for local dev
// and any environment that hasn't set the runtime vars yet. `||` (not `??`)
// so an accidentally-empty SUPABASE_URL still falls back to the baked value
// instead of crashing the server with an empty-URL Supabase init.
const supabaseUrl =
   process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey =
   process.env.SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl) {
   throw new Error(
      "SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL fallback) is not set",
   );
}

if (!supabaseAnonKey) {
   throw new Error(
      "SUPABASE_ANON_KEY (or NEXT_PUBLIC_SUPABASE_ANON_KEY fallback) is not set",
   );
}

export const createSupabaseServerClient = async () => {
   const cookieStore = await cookies();

   return createServerClient(supabaseUrl, supabaseAnonKey, {
      cookies: {
         getAll() {
            return cookieStore.getAll();
         },
         setAll(cookiesToSet) {
            cookiesToSet.forEach(({ name, value, options }) => {
               try {
                  cookieStore.set(name, value, options);
               } catch (error) {
                  console.error("Failed to set Supabase cookie", { name }, error);
               }
            });
         },
      },
   });
};
