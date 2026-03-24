// Plausible-compatible analytics wrapper -- no-op in development
type EventName = "waitlist_signup" | "workflow_created" | "template_installed" | "share_created";

interface PlausibleWindow extends Window {
  plausible?: (event: string, options?: { props?: Record<string, string> }) => void;
}

export function trackEvent(name: EventName, props?: Record<string, string>): void {
  if (typeof window === "undefined") return;
  if (process.env.NODE_ENV !== "production") return;

  const w = window as PlausibleWindow;
  w.plausible?.(name, props ? { props } : undefined);
}
