"use client";
import { useTheme } from "@/hooks/useTheme";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const next = theme === "light" ? "dark" : "light";

  return (
    <button
      onClick={() => setTheme(next)}
      aria-label={`Switch to ${next} mode`}
      style={{
        padding: "4px 8px",
        borderRadius: 4,
        border: "1px solid var(--color-border)",
        backgroundColor: "transparent",
        color: "var(--color-text-secondary)",
        fontFamily: "var(--font-mono)",
        fontSize: 10,
        cursor: "pointer",
      }}
    >
      {theme === "light" ? "Dark" : "Light"}
    </button>
  );
}
