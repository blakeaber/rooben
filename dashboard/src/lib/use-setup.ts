"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from "react";
import React from "react";

const SETUP_DONE_KEY = "rooben_setup_complete";

interface SetupContextValue {
  setupComplete: boolean;
  completeSetup: () => void;
  resetSetup: () => void;
}

const SetupContext = createContext<SetupContextValue>({
  setupComplete: false,
  completeSetup: () => {},
  resetSetup: () => {},
});

export function SetupProvider({ children }: { children: ReactNode }) {
  // Always start false to match SSR; sync from localStorage after mount
  const [setupComplete, setSetupComplete] = useState(false);

  useEffect(() => {
    if (localStorage.getItem(SETUP_DONE_KEY) === "true") {
      setSetupComplete(true);
    }
  }, []);

  const completeSetup = useCallback(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem(SETUP_DONE_KEY, "true");
    }
    setSetupComplete(true);
  }, []);

  const resetSetup = useCallback(() => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(SETUP_DONE_KEY);
    }
    setSetupComplete(false);
  }, []);

  return React.createElement(
    SetupContext.Provider,
    { value: { setupComplete, completeSetup, resetSetup } },
    children
  );
}

export function useSetup() {
  return useContext(SetupContext);
}
