"use client";

import { useState, useEffect } from "react";
import { useSetup } from "@/lib/use-setup";
import { isProEnabled } from "@/lib/pro-loader";
import { SetupWizard } from "./SetupWizard";
import { apiFetch } from "@/lib/api";

interface SetupGateProps {
  children: React.ReactNode;
}

type ProAuthState = "checking" | "needs_login" | "needs_onboarding" | "ready";

export function SetupGate({ children }: SetupGateProps) {
  const { setupComplete } = useSetup();
  const [proState, setProState] = useState<ProAuthState>("checking");

  useEffect(() => {
    if (!isProEnabled) return;

    // Don't redirect if already on auth/onboarding pages
    const path = typeof window !== "undefined" ? window.location.pathname : "";
    if (path.startsWith("/pro/login") || path.startsWith("/pro/onboarding")) {
      setProState("ready");
      return;
    }

    const hasToken =
      typeof window !== "undefined" &&
      (localStorage.getItem("rooben_session") || localStorage.getItem("rooben_api_key"));

    if (!hasToken) {
      setProState("needs_login");
      return;
    }

    apiFetch<{ onboarding_complete?: boolean }>("/api/auth/me")
      .then((data) => {
        if (data.onboarding_complete) {
          setProState("ready");
        } else {
          setProState("needs_onboarding");
        }
      })
      .catch(() => {
        setProState("needs_login");
      });
  }, []);

  useEffect(() => {
    if (!isProEnabled) return;
    if (proState === "needs_login") {
      window.location.href = "/pro/login";
    } else if (proState === "needs_onboarding") {
      window.location.href = "/pro/onboarding/goals";
    }
  }, [proState]);

  // Pro mode: route based on auth + onboarding state
  if (isProEnabled) {
    if (proState === "ready") {
      return <>{children}</>;
    }
    // Show loading while checking or redirecting
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
        <p style={{ color: "var(--color-text-secondary)", fontSize: 14 }}>Loading...</p>
      </div>
    );
  }

  // OSS mode: original behavior
  if (!setupComplete) {
    return <SetupWizard />;
  }

  return <>{children}</>;
}
