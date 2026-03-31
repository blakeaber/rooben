/**
 * Pro sidebar navigation loader.
 *
 * Dynamically loads Pro nav groups from the @rooben-pro/dashboard webpack alias.
 * When Pro is not installed, returns an empty array (no nav items added).
 *
 * Nav items are prefixed with /pro/ to route through the catch-all page.
 */

import { isProEnabled } from "@/pro/loader";

interface NavItem {
  href: string;
  label: string;
  icon: string;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

/**
 * Load Pro navigation groups, prefixed with /pro/ for catch-all routing.
 * Returns [] when Pro is not installed — safe to spread into NAV_GROUPS.
 */
export function loadProNavGroups(): NavGroup[] {
  if (!isProEnabled) return [];

  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const proConfig = require("@rooben-pro/dashboard/components/layout/sidebar-nav-config");
    return (proConfig.PRO_NAV_GROUPS ?? []).map((group: NavGroup) => ({
      ...group,
      items: group.items.map((item: NavItem) => ({
        ...item,
        href: `/pro${item.href}`,
      })),
    }));
  } catch {
    // Pro webpack alias not available — no nav items added
    return [];
  }
}
