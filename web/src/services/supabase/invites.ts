"use client";

import { createSupabaseBrowserClient } from "@/src/db/client";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { Invite, CreateInviteDbParams } from "@/src/types/auth";

export const createInvitesService = (client: SupabaseClient = createSupabaseBrowserClient()) => ({
  create: (params: CreateInviteDbParams) =>
    client.from("invites").insert({
      org_id: params.orgId,
      email: params.email,
      role: params.role,
      token_hash: params.tokenHash,
      expires_at: params.expiresAt.toISOString(),
    }).select().single<Invite>(),

  getByTokenHash: (tokenHash: string) =>
    client.from("invites").select("*").eq("token_hash", tokenHash).is("used_at", null).single<Invite>(),

  getByOrgId: (orgId: string) =>
    client.from("invites").select("*").eq("org_id", orgId).is("used_at", null).order("created_at", { ascending: false }),

  markAsUsed: (inviteId: string) =>
    client.from("invites").update({ used_at: new Date().toISOString() }).eq("id", inviteId),

  delete: (inviteId: string) =>
    client.from("invites").delete().eq("id", inviteId),
});

export const invitesService = createInvitesService();
