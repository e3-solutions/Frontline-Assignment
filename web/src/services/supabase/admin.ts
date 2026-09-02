import { createClient, SupabaseClient } from "@supabase/supabase-js";
import type { CreateUserParams, LoginCredentials } from "@/src/types/auth";

// Admin client runs server-side only. Prefer the runtime-only SUPABASE_URL
// (set in Railway alongside SUPABASE_SERVICE_ROLE_KEY) so prod can switch
// projects without rebuilding the image; fall back to the build-time-baked
// NEXT_PUBLIC_SUPABASE_URL for local dev. `||` (not `??`) so an empty runtime
// var still falls back to the baked value.
const adminSupabaseUrl =
  process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL!;

const supabaseAdmin = createClient(
  adminSupabaseUrl,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export const createAdminServices = (client: SupabaseClient = supabaseAdmin) => ({
  auth: {
    createUser: ({ email, password }: LoginCredentials) =>
      client.auth.admin.createUser({ email, password, email_confirm: true }),
    deleteUser: (userId: string) => client.auth.admin.deleteUser(userId),
  },
  users: {
    create: (params: CreateUserParams) =>
      client.from("users").insert({
        user_id: params.userId,
        full_name: params.fullName,
        org_id: params.orgId,
        role: params.role,
      }),
    getByOrgId: (orgId: string) =>
      client.from("users").select("*").eq("org_id", orgId).order("created_at", { ascending: false }),
    getById: (userId: string) =>
      client.from("users").select("*").eq("user_id", userId).single(),
  },
  organizations: {
    create: (name: string) =>
      client.from("organizations").insert({ name }).select().single(),
    delete: (id: string) => client.from("organizations").delete().eq("id", id),
  },
  invites: {
    getByTokenHash: (tokenHash: string) =>
      client
        .from("invites")
        .select("*")
        .eq("token_hash", tokenHash)
        .is("used_at", null)
        .single(),
    markAsUsed: (inviteId: string) =>
      client
        .from("invites")
        .update({ used_at: new Date().toISOString() })
        .eq("id", inviteId),
  },
});

export const adminServices = createAdminServices();
