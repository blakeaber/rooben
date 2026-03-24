"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { apiFetch } from "@/lib/api";

export interface UserIdentity {
  id: string;
  is_anonymous: boolean;
}

export type ConnectionStatus = "checking" | "connected" | "disconnected";

interface ConnectionContextValue {
  user: UserIdentity | null;
  status: ConnectionStatus;
  recheck: () => Promise<void>;
}

const ConnectionContext = createContext<ConnectionContextValue>({
  user: null,
  status: "checking",
  recheck: async () => {},
});

export function ConnectionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserIdentity | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("checking");

  const recheck = useCallback(async () => {
    setStatus("checking");
    try {
      const identity = await apiFetch<UserIdentity>("/api/me/identity");
      setUser(identity);
      setStatus("connected");
    } catch {
      setUser(null);
      setStatus("disconnected");
    }
  }, []);

  useEffect(() => {
    recheck();
  }, [recheck]);

  return (
    <ConnectionContext.Provider value={{ user, status, recheck }}>
      {children}
    </ConnectionContext.Provider>
  );
}

export function useConnection() {
  return useContext(ConnectionContext);
}
