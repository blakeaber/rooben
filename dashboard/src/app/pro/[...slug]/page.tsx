"use client";

import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import { isProEnabled } from "@/lib/pro-loader";

/**
 * Map of Pro page paths to their dynamic import loaders.
 * Each key matches a URL path segment after /pro/.
 */
const PRO_PAGES: Record<string, ReturnType<typeof dynamic>> = isProEnabled
  ? {
      "onboarding/goals": dynamic(
        () => import("@rooben-pro/dashboard/app/onboarding/goals/page")
      ),
      "onboarding/provider": dynamic(
        () => import("@rooben-pro/dashboard/app/onboarding/provider/page")
      ),
      "onboarding/start": dynamic(
        () => import("@rooben-pro/dashboard/app/onboarding/start/page")
      ),
      learnings: dynamic(
        () => import("@rooben-pro/dashboard/app/learnings/page")
      ),
      agents: dynamic(
        () => import("@rooben-pro/dashboard/app/agents/page")
      ),
      "agents/profile": dynamic(
        () => import("@rooben-pro/dashboard/app/agents/profile/page")
      ),
      delegations: dynamic(
        () => import("@rooben-pro/dashboard/app/delegations/page")
      ),
      route: dynamic(
        () => import("@rooben-pro/dashboard/app/route/page")
      ),
      "org-dashboard": dynamic(
        () => import("@rooben-pro/dashboard/app/org-dashboard/page")
      ),
      login: dynamic(
        () => import("@rooben-pro/dashboard/app/login/page")
      ),
      billing: dynamic(
        () => import("@rooben-pro/dashboard/app/billing/page")
      ),
      settings: dynamic(
        () => import("@rooben-pro/dashboard/app/settings/page")
      ),
      audit: dynamic(
        () => import("@rooben-pro/dashboard/app/audit/page")
      ),
      workspace: dynamic(
        () => import("@rooben-pro/dashboard/app/workspace/page")
      ),
      workflows: dynamic(
        () => import("@rooben-pro/dashboard/app/workflows/page")
      ),
      "org/members": dynamic(
        () => import("@rooben-pro/dashboard/app/org/members/page")
      ),
      "org/policies": dynamic(
        () => import("@rooben-pro/dashboard/app/org/policies/page")
      ),
      "org/templates": dynamic(
        () => import("@rooben-pro/dashboard/app/org/templates/page")
      ),
      "org/dashboard": dynamic(
        () => import("@rooben-pro/dashboard/app/org/dashboard/page")
      ),
    }
  : {};

export default function ProCatchAllPage() {
  const params = useParams<{ slug: string[] }>();
  const path = params.slug?.join("/") ?? "";

  if (!isProEnabled) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <h1 className="text-xl font-semibold mb-2">Pro Feature</h1>
          <p style={{ color: "var(--color-text-secondary)" }}>
            This feature requires Rooben Pro.
          </p>
        </div>
      </div>
    );
  }

  const Component = PRO_PAGES[path];
  if (!Component) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <h1 className="text-xl font-semibold mb-2">Page Not Found</h1>
          <p style={{ color: "var(--color-text-secondary)" }}>
            The Pro page &ldquo;/pro/{path}&rdquo; does not exist.
          </p>
        </div>
      </div>
    );
  }

  return <Component />;
}
