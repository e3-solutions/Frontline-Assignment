"use client";

import { authService } from "@/src/services/supabase/auth";
import { usersService } from "@/src/services/supabase/users";
import { organizationsService } from "@/src/services/supabase/organizations";
import { invitesService } from "@/src/services/supabase/invites";
import type {
  LoginCredentials,
  RegisterCompanyData,
  RegisterUserData,
  UserProfile,
  InviteResult,
  CreateInviteParams,
  AuthStateCallback,
  UserRole,
} from "@/src/types/auth";

const hashToken = async (token: string): Promise<string> => {
  const encoder = new TextEncoder();
  const data = encoder.encode(token);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
};

const generateToken = (): string => {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return Array.from(array, (b) => b.toString(16).padStart(2, "0")).join("");
};

export const login = async (params: LoginCredentials): Promise<void> => {
  const { error } = await authService.signIn(params);
  if (error) throw new Error(error.message);
};

export const logout = async (): Promise<void> => {
  const { error } = await authService.signOut();
  if (error) throw new Error(error.message);
};

export const registerCompany = async (params: RegisterCompanyData): Promise<void> => {
  const response = await fetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "company", ...params }),
  });

  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Registration failed");

  await login({ email: params.email, password: params.password });
};

export const registerUser = async (params: RegisterUserData): Promise<void> => {
  const response = await fetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "invite", ...params }),
  });

  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Registration failed");

  await login({ email: params.email, password: params.password });
};

export const createInvite = async (params: CreateInviteParams): Promise<InviteResult> => {
  const token = generateToken();
  const tokenHash = await hashToken(token);
  const expiresAt = new Date();
  expiresAt.setDate(expiresAt.getDate() + 7);

  const { data, error } = await invitesService.create({
    orgId: params.orgId,
    email: params.email,
    role: params.role,
    tokenHash,
    expiresAt,
  });

  if (error || !data) throw new Error(error?.message || "Failed to create invitation");

  return { inviteId: data.id, token, expiresAt };
};

export const validateInvite = async (token: string): Promise<{ email: string; role: string } | null> => {
  const tokenHash = await hashToken(token);
  const { data: invite, error } = await invitesService.getByTokenHash(tokenHash);

  if (error || !invite) return null;
  if (new Date(invite.expires_at) < new Date()) return null;

  return { email: invite.email, role: invite.role };
};

export const fetchUserProfile = async (userId: string, email?: string): Promise<UserProfile | null> => {
  const { data: userData, error: userError } = await usersService.getById(userId);
  if (userError || !userData) return null;

  const { data: orgData, error: orgError } = await organizationsService.getById(userData.org_id);
  if (orgError || !orgData) return null;

  return { user: { ...userData, email }, organization: orgData };
};

export const getSession = () => authService.getSession();

export const onAuthStateChange = (callback: AuthStateCallback) =>
  authService.onAuthStateChange(callback);

export const checkSuperadminExists = () => usersService.checkSuperadminExists();

export interface CreateUserAccountParams {
  email: string;
  password: string;
  fullName: string;
  role: UserRole;
  orgId: string;
}

export const createUserAccount = async (params: CreateUserAccountParams): Promise<void> => {
  const response = await fetch("/api/auth/create-user", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });

  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Failed to create user account");
};
