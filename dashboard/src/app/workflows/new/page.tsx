"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { CreateWorkflowWizard } from "@/components/create/CreateWorkflowWizard";

function NewWorkflowContent() {
  const searchParams = useSearchParams();
  const persona = searchParams.get("persona");

  return (
    <div
      style={{
        backgroundColor: "var(--color-surface-1)",
        minHeight: "100vh",
        padding: "0 0 48px",
      }}
    >
      <Header
        title="New Workflow"
        breadcrumbs={[
          { label: "Workflows", href: "/" },
          { label: "New" },
        ]}
      />
      <CreateWorkflowWizard persona={persona} />
    </div>
  );
}

export default function NewWorkflowPage() {
  return (
    <Suspense>
      <NewWorkflowContent />
    </Suspense>
  );
}
