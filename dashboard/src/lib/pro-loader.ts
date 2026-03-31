/**
 * Pro dashboard loader — detects whether Pro frontend is available.
 *
 * Pro is enabled when ROOBEN_PRO_DASHBOARD_DIR env var is set,
 * pointing to the rooben-pro dashboard/src directory.
 */

export const PRO_DIR = process.env.ROOBEN_PRO_DASHBOARD_DIR || process.env.NEXT_PUBLIC_PRO_ENABLED || "";
export const isProEnabled = !!PRO_DIR;
