"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import {
  fetchUserProfile,
  getSession,
  onAuthStateChange,
  logout as authLogout,
} from "@/src/services/auth";
import type { AuthState, User, Organization } from "@/src/types/auth";

interface AuthContextValue extends AuthState {
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadProfile = useCallback(async (userId: string, email?: string) => {
    const profile = await fetchUserProfile(userId, email);
    if (profile) {
      setUser(profile.user);
      setOrganization(profile.organization);
    } else {
      setUser(null);
      setOrganization(null);
    }
  }, []);

  const refreshProfile = useCallback(async () => {
    if (user?.user_id) {
      await loadProfile(user.user_id, user.email);
    }
  }, [user, loadProfile]);

  useEffect(() => {
    // Get initial session
    getSession().then(({ data }) => {
      if (data.session?.user) {
        loadProfile(data.session.user.id, data.session.user.email ?? undefined).finally(
          () => {
            setIsLoading(false);
          }
        );
      } else {
        setIsLoading(false);
      }
    });

    // Subscribe to auth changes
    const { unsubscribe } = onAuthStateChange((userId, email) => {
      if (userId) {
        loadProfile(userId, email ?? undefined);
      } else {
        setUser(null);
        setOrganization(null);
      }
    });

    return unsubscribe;
  }, [loadProfile]);

  const logout = async () => {
    await authLogout();
    setUser(null);
    setOrganization(null);
  };

  const value: AuthContextValue = {
    user,
    organization,
    isLoading,
    isAuthenticated: !!user,
    isSuperadmin: user?.is_superadmin ?? false,
    logout,
    refreshProfile,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
