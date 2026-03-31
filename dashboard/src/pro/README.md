# Pro Integration Hooks

This directory contains all Rooben Pro integration code for the OSS dashboard.

**No Pro business logic lives here** — only the hooks that allow the OSS dashboard
to detect, load, and route to Pro features when the Pro extension is installed.

## Files

| File | Purpose | Used by |
|------|---------|---------|
| `loader.ts` | `isProEnabled` flag — checks env var | All other Pro hooks |
| `hooks.ts` | `useProAuth()` — auth + onboarding state machine | `SetupGate.tsx` |
| `nav-config.ts` | `loadProNavGroups()` — sidebar nav items from Pro | `Sidebar.tsx` |

## How it works

1. **Detection**: `loader.ts` checks `ROOBEN_PRO_DASHBOARD_DIR` or `NEXT_PUBLIC_PRO_ENABLED`
2. **Routing**: `hooks.ts` checks auth state via `/api/auth/me` and redirects to login/onboarding
3. **Navigation**: `nav-config.ts` dynamically loads Pro sidebar items via webpack alias
4. **Pages**: `src/app/pro/[...slug]/page.tsx` catch-all dynamically imports Pro page components

## For OSS users (Pro not installed)

- `isProEnabled` returns `false`
- `useProAuth()` returns `"ready"` immediately (no-op)
- `loadProNavGroups()` returns `[]` (no extra nav items)
- `/pro/*` routes show "This feature requires Rooben Pro"
- Zero performance impact — Pro imports are never loaded
