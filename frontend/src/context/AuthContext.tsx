import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from "react";
import * as api from "../lib/api";
import type { User } from "../lib/api";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  // Starts true: on first mount we don't yet know if a stored token is still
  // valid, so routes must wait for this to resolve before deciding whether
  // to bounce someone to /login.
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    if (!api.getAccessToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.getMe();
      setUser(me);
    } catch {
      // Token was present but invalid/expired past the point request()'s
      // own refresh-and-retry could save it.
      api.clearTokens();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const login = useCallback(async (email: string, password: string) => {
    await api.login(email, password);
    await loadUser();
  }, [loadUser]);

  const register = useCallback(async (email: string, password: string) => {
    await api.register(email, password);
    await loadUser();
  }, [loadUser]);

  const logout = useCallback(() => {
    api.logout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
