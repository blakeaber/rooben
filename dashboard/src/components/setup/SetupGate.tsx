"use client";

import { useSetup } from "@/lib/use-setup";
import { SetupWizard } from "./SetupWizard";

interface SetupGateProps {
  children: React.ReactNode;
}

export function SetupGate({ children }: SetupGateProps) {
  const { setupComplete } = useSetup();

  if (!setupComplete) {
    return <SetupWizard />;
  }

  return <>{children}</>;
}
