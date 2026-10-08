"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, Me, setCsrf } from "@/lib/api";

interface SessionValue { me: Me | null; loading: boolean; refresh: () => Promise<void>; signOut: () => Promise<void>; }
const Ctx = createContext<SessionValue>({ me: null, loading: true, refresh: async () => {}, signOut: async () => {} });

export function SessionProvider({ children, requireMfa = true }: { children: React.ReactNode; requireMfa?: boolean }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const refresh = useCallback(async () => {
    try {
      const m = await api.get<Me>("/me");
      setCsrf(m.csrf_token);
      setMe(m);
      if (requireMfa && m.mfa.required && !m.mfa.passed) router.replace("/mfa");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.replace("/sign-in");
    } finally {
      setLoading(false);
    }
  }, [router, requireMfa]);

  const signOut = useCallback(async () => {
    try { await api.post("/auth/logout"); } finally { router.replace("/sign-in"); }
  }, [router]);

  useEffect(() => { void refresh(); }, [refresh]);
  return <Ctx.Provider value={{ me, loading, refresh, signOut }}>{children}</Ctx.Provider>;
}

export const useSession = () => useContext(Ctx);
