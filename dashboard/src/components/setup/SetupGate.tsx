"use client";

import { useSetup } from "@/lib/use-setup";
import { isProEnabled } from "@/pro/loader";
import { useProAuth } from "@/pro/hooks";
import { SetupWizard } from "./SetupWizard";

interface SetupGateProps {
  children: React.ReactNode;
}

export function SetupGate({ children }: SetupGateProps) {
  const { setupComplete } = useSetup();
  const proState = useProAuth();

  // Pro mode: route based on auth + onboarding state (logic in @/pro/hooks)
  if (isProEnabled) {
    if (proState === "ready") {
      return <>{children}</>;
    }
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
