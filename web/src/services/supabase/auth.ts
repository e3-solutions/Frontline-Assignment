"use client";

import { createSupabaseBrowserClient } from "@/src/db/client";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { LoginCredentials, AuthStateCallback } from "@/src/types/auth";

export const createAuthService = (client: SupabaseClient = createSupabaseBrowserClient()) => ({
  signUp: ({ email, password }: LoginCredentials) =>
    client.auth.signUp({ email, password }),

  signIn: ({ email, password }: LoginCredentials) =>
    client.auth.signInWithPassword({ email, password }),

  signOut: () => client.auth.signOut(),

  getSession: () => client.auth.getSession(),

  onAuthStateChange: (callback: AuthStateCallback) => {
    const { data: { subscription } } = client.auth.onAuthStateChange((_event, session) => {
      callback(session?.user?.id ?? null, session?.user?.email ?? null);
    });
    return { unsubscribe: subscription.unsubscribe };
  },
});

export const authService = createAuthService();
