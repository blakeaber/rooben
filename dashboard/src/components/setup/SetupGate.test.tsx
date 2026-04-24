import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// The hook reads a localStorage key after mount and re-renders. We control
// that via the storage API directly — the real SetupProvider reads the key.
// SetupWizard is heavy (mounts network fixtures); stub it to a marker.
vi.mock("./SetupWizard", () => ({
  SetupWizard: () => <div data-testid="setup-wizard">Setup Wizard</div>,
}));

import { SetupProvider } from "@/lib/use-setup";
import { SetupGate } from "./SetupGate";

const SETUP_DONE_KEY = "rooben_setup_complete";

// Install a minimal Storage polyfill onto window.localStorage. Node 22+
// ships a built-in global `localStorage` without `.clear()` that shadows
// jsdom's when vitest runs, and replacing it reliably requires overriding
// the descriptor each test run.
class MemoryStorage implements Storage {
  private data = new Map<string, string>();
  get length(): number {
    return this.data.size;
  }
  clear(): void {
    this.data.clear();
  }
  getItem(key: string): string | null {
    return this.data.has(key) ? (this.data.get(key) as string) : null;
  }
  setItem(key: string, value: string): void {
    this.data.set(key, String(value));
  }
  removeItem(key: string): void {
    this.data.delete(key);
  }
  key(i: number): string | null {
    return Array.from(this.data.keys())[i] ?? null;
  }
}

beforeEach(() => {
  Object.defineProperty(window, "localStorage", {
    value: new MemoryStorage(),
    configurable: true,
    writable: false,
  });
});

const storage = () => window.localStorage;

function clearStorage() {
  storage().clear();
}

describe("SetupGate", () => {
  afterEach(clearStorage);

  it("renders the SetupWizard when setup is not complete", () => {
    render(
      <SetupProvider>
        <SetupGate>
          <div data-testid="child">Protected content</div>
        </SetupGate>
      </SetupProvider>,
    );
    expect(screen.getByTestId("setup-wizard")).toBeInTheDocument();
    expect(screen.queryByTestId("child")).not.toBeInTheDocument();
  });

  it("renders children when setup is marked complete in localStorage", async () => {
    storage().setItem(SETUP_DONE_KEY, "true");
    render(
      <SetupProvider>
        <SetupGate>
          <div data-testid="child">Protected content</div>
        </SetupGate>
      </SetupProvider>,
    );
    // The hook syncs from localStorage via a useEffect after mount
    expect(await screen.findByTestId("child")).toBeInTheDocument();
    expect(screen.queryByTestId("setup-wizard")).not.toBeInTheDocument();
  });

  it("gates multiple children behind the same setup check", async () => {
    storage().setItem(SETUP_DONE_KEY, "true");
    render(
      <SetupProvider>
        <SetupGate>
          <span>first</span>
          <span>second</span>
        </SetupGate>
      </SetupProvider>,
    );
    expect(await screen.findByText("first")).toBeInTheDocument();
    expect(screen.getByText("second")).toBeInTheDocument();
  });
});
