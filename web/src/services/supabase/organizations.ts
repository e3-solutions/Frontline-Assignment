"use client";

import { createSupabaseBrowserClient } from "@/src/db/client";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { Organization } from "@/src/types/auth";

export const createOrganizationsService = (client: SupabaseClient = createSupabaseBrowserClient()) => ({
  create: (name: string) =>
    client.from("organizations").insert({ name }).select().single<Organization>(),

  getById: (orgId: string) =>
    client.from("organizations").select("*").eq("id", orgId).single<Organization>(),

  update: (orgId: string, updates: Partial<Pick<Organization, "name">>) =>
    client.from("organizations").update(updates).eq("id", orgId).select().single<Organization>(),

  delete: (orgId: string) =>
    client.from("organizations").delete().eq("id", orgId),
});

export const organizationsService = createOrganizationsService();
