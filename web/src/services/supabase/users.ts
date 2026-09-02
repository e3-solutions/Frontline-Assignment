"use client";

import { createSupabaseBrowserClient } from "@/src/db/client";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { User, CreateUserParams } from "@/src/types/auth";

export const createUsersService = (client: SupabaseClient = createSupabaseBrowserClient()) => ({
  create: (params: CreateUserParams) =>
    client.from("users").insert({
      user_id: params.userId,
      full_name: params.fullName,
      org_id: params.orgId,
      role: params.role,
    }).select().single<User>(),

  getById: (userId: string) =>
    client.from("users").select("*").eq("user_id", userId).single<User>(),

  getByOrgId: (orgId: string) =>
    client.from("users").select("*").eq("org_id", orgId).order("created_at", { ascending: false }),

  update: (userId: string, updates: Partial<Pick<User, "full_name" | "role">>) =>
    client.from("users").update(updates).eq("user_id", userId).select().single<User>(),

  checkSuperadminExists: async () => {
    const { data, error } = await client.from("users").select("user_id").eq("is_superadmin", true).limit(1);
    if (error) return false;
    return data && data.length > 0;
  },

  setSuperadminFlag: (userId: string) =>
    client.from("users").update({ is_superadmin: true }).eq("user_id", userId),
});

export const usersService = createUsersService();
