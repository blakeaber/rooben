"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * The Browse Library is now integrated directly into the Integrations Hub page.
 * Redirect any old links to /integrations.
 */
export default function LibraryRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/integrations");
  }, [router]);

  return (
    <div
      style={{
        padding: "60px",
        textAlign: "center",
        fontFamily: "var(--font-mono)",
        fontSize: "11px",
        color: "var(--color-text-muted)",
      }}
    >
      Redirecting...
    </div>
  );
}
