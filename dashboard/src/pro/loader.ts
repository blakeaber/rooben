/**
 * Pro feature detection.
 *
 * Returns true when the Rooben Pro dashboard extension is installed
 * (ROOBEN_PRO_DASHBOARD_DIR or NEXT_PUBLIC_PRO_ENABLED env var set).
 *
 * This is the single source of truth for "is Pro available?" —
 * all other Pro integration code checks this flag before executing.
 */

export const PRO_DIR = process.env.ROOBEN_PRO_DASHBOARD_DIR || process.env.NEXT_PUBLIC_PRO_ENABLED || "";
export const isProEnabled = !!PRO_DIR;
