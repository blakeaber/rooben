"use client";

import { useSetup } from "@/lib/use-setup";
import { isProEnabled } from "@/lib/pro-loader";
import { SetupWizard } from "./SetupWizard";

interface SetupGateProps {
  children: React.ReactNode;
}

export function SetupGate({ children }: SetupGateProps) {
  const { setupComplete } = useSetup();

  // Pro mode: skip LLM provider setup — Pro manages auth server-side
  if (isProEnabled) {
    return <>{children}</>;
  }

  if (!setupComplete) {
    return <SetupWizard />;
  }

  return <>{children}</>;
}
