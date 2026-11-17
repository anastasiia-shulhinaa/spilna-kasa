import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setUnauthorizedHandler, tokenStore } from "../api/client";
import type { User } from "../api/types";

interface AuthState {
  token: string | null;
  user: User | undefined;
  loading: boolean;
  signIn: (token: string) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [token, setToken] = useState<string | null>(() => tokenStore.get());

  const signIn = useCallback(
    (t: string) => {
      tokenStore.set(t);
      qc.clear();
      setToken(t);
    },
    [qc],
  );

  const signOut = useCallback(() => {
    tokenStore.set(null);
    qc.clear();
    setToken(null);
  }, [qc]);

  useEffect(() => setUnauthorizedHandler(signOut), [signOut]);

  const me = useQuery({ queryKey: ["me", token], queryFn: api.me, enabled: !!token });

  const value = useMemo(
    () => ({ token, user: me.data, loading: !!token && me.isLoading, signIn, signOut }),
    [token, me.data, me.isLoading, signIn, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
