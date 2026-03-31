/**
 * Pro authentication and onboarding hooks.
 *
 * Used by SetupGate to determine whether a Pro user needs to:
 * - Log in (no session token)
 * - Complete onboarding (logged in but onboarding_complete !== true)
 * - Proceed to dashboard (fully onboarded)
 *
 * Returns a state machine value that the gate component can render against.
 */

"use client";

import { useState, useEffect } from "react";
import { isProEnabled } from "@/pro/loader";
import { apiFetch } from "@/lib/api";

export type ProAuthState = "checking" | "needs_login" | "needs_onboarding" | "ready";

/**
 * Hook that resolves Pro auth + onboarding state.
 *
 * - Pages under /pro/login and /pro/onboarding bypass checks (returns "ready").
 * - No token in localStorage → "needs_login"
 * - Token present but /api/auth/me says onboarding incomplete → "needs_onboarding"
 * - Token present + onboarding complete → "ready"
 * - Any API error → "needs_login" (token expired/invalid)
 */
export function useProAuth(): ProAuthState {
  const [state, setState] = useState<ProAuthState>("checking");

  useEffect(() => {
    if (!isProEnabled) {
      setState("ready");
      return;
    }

    // Auth/onboarding pages render without checks (avoids redirect loops)
    const path = typeof window !== "undefined" ? window.location.pathname : "";
    if (path.startsWith("/pro/login") || path.startsWith("/pro/onboarding")) {
      setState("ready");
      return;
    }

    const hasToken =
      typeof window !== "undefined" &&
      (localStorage.getItem("rooben_session") || localStorage.getItem("rooben_api_key"));

    if (!hasToken) {
      setState("needs_login");
      return;
    }

    apiFetch<{ onboarding_complete?: boolean }>("/api/auth/me")
      .then((data) => {
        setState(data.onboarding_complete ? "ready" : "needs_onboarding");
      })
      .catch(() => {
        setState("needs_login");
      });
  }, []);

  // Handle redirects
  useEffect(() => {
    if (!isProEnabled) return;
    if (state === "needs_login") {
      window.location.href = "/pro/login";
    } else if (state === "needs_onboarding") {
      window.location.href = "/pro/onboarding/goals";
    }
  }, [state]);

  return state;
}
