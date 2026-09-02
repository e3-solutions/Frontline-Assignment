export type UserRole = "admin" | "employee";

export interface Organization {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface User {
  user_id: string;
  full_name: string;
  org_id: string;
  role: UserRole;
  is_superadmin: boolean;
  created_at: string;
  updated_at: string;
  email?: string;
}

export interface AuthState {
  user: User | null;
  organization: Organization | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isSuperadmin: boolean;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterCompanyData {
  email: string;
  password: string;
  fullName: string;
  organizationName: string;
  companySecret: string;
}

export interface RegisterUserData {
  email: string;
  password: string;
  fullName: string;
  inviteToken: string;
}

export interface Invite {
  id: string;
  org_id: string;
  email: string;
  role: UserRole;
  token_hash: string;
  used_at: string | null;
  expires_at: string;
  created_at: string;
}

export interface CreateUserParams {
  userId: string;
  fullName: string;
  orgId: string;
  role: UserRole;
}

export interface CreateInviteParams {
  orgId: string;
  email: string;
  role: UserRole;
}

export interface CreateInviteDbParams extends CreateInviteParams {
  tokenHash: string;
  expiresAt: Date;
}

export interface InviteResult {
  inviteId: string;
  token: string;
  expiresAt: Date;
}

export type AuthStateCallback = (userId: string | null, email: string | null) => void;

export interface UserProfile {
  user: User;
  organization: Organization;
}

export interface PhoneNumber {
  phone_number: string;
  org_id: string;
  label: string | null;
  created_at: string;
}
