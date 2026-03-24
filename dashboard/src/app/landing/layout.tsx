"use client";

import { useEffect } from "react";

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Hide the parent dashboard sidebar and reset the layout for full-width
  useEffect(() => {
    // Hide sidebar
    const sidebar = document.querySelector("aside[aria-label='Main navigation']") as HTMLElement;
    if (sidebar) sidebar.style.display = "none";

    // Make parent main full-width and remove padding/background
    const main = document.querySelector("main") as HTMLElement;
    if (main) {
      main.style.padding = "0";
      main.style.backgroundColor = "transparent";
    }

    // Make body dark for marketing
    document.body.style.backgroundColor = "#0a0e1a";
    document.body.style.color = "#f1f5f9";

    return () => {
      if (sidebar) sidebar.style.display = "";
      if (main) {
        main.style.padding = "";
        main.style.backgroundColor = "";
      }
      document.body.style.backgroundColor = "";
      document.body.style.color = "";
    };
  }, []);

  return (
    <div data-theme="dark">
      {/* Top navigation */}
      <nav
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          zIndex: 50,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "16px 32px",
          background: "rgba(10, 14, 26, 0.8)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 28,
              height: 28,
              borderRadius: 6,
              background: "var(--gradient-rooben)",
              backgroundSize: "200% 200%",
              color: "#ffffff",
              fontFamily: "var(--font-mono)",
              fontSize: 13,
              fontWeight: 700,
            }}
          >
            R
          </span>
          <span
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: 18,
              fontWeight: 700,
              letterSpacing: "-0.01em",
              color: "#f1f5f9",
            }}
          >
            Rooben
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
          <a
            href="#features"
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: 14,
              color: "#94a3b8",
              textDecoration: "none",
              transition: "color 0.15s ease",
            }}
          >
            Features
          </a>
          <a
            href="#demo"
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: 14,
              color: "#94a3b8",
              textDecoration: "none",
              transition: "color 0.15s ease",
            }}
          >
            Demo
          </a>
          <a
            href="#compare"
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: 14,
              color: "#94a3b8",
              textDecoration: "none",
              transition: "color 0.15s ease",
            }}
          >
            Compare
          </a>
          <a
            href="https://github.com/blakeaber/rooben"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: 13,
              color: "#94a3b8",
              textDecoration: "none",
              padding: "8px 14px",
              borderRadius: 6,
              border: "1px solid rgba(255,255,255,0.1)",
              transition: "all 0.15s ease",
            }}
          >
            GitHub
          </a>
          <a
            href="#waitlist"
            className="rooben-cta"
            style={{ padding: "8px 18px", fontSize: 13 }}
          >
            Join Waitlist
          </a>
        </div>
      </nav>

      <div
        style={{
          backgroundColor: "#0a0e1a",
          color: "#f1f5f9",
          fontFamily: "var(--font-ui)",
          minHeight: "100vh",
          scrollBehavior: "smooth",
        }}
      >
        {children}
      </div>
    </div>
  );
}
