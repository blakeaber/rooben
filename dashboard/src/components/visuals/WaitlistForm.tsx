"use client";

import { useState } from "react";

interface WaitlistFormProps {
  variant?: "inline" | "block";
}

export function WaitlistForm({ variant = "inline" }: WaitlistFormProps) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [position, setPosition] = useState<number | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || status === "loading") return;

    setStatus("loading");
    try {
      const res = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });

      if (res.ok) {
        const data = await res.json();
        setPosition(data.position ?? null);
        setStatus("success");
      } else {
        setStatus("error");
      }
    } catch {
      setStatus("error");
    }
  };

  if (status === "success") {
    return (
      <div
        className="animate-fade-in"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "12px 20px",
          borderRadius: 8,
          background: "rgba(22, 163, 74, 0.1)",
          border: "1px solid rgba(22, 163, 74, 0.2)",
          color: "#4ade80",
          fontFamily: "var(--font-ui)",
          fontSize: 14,
          fontWeight: 500,
        }}
      >
        <span className="animate-check-pop" style={{ fontSize: 18 }}>
          &#10003;
        </span>
        You&apos;re on the list!{position ? ` (#${position})` : ""}
      </div>
    );
  }

  const isInline = variant === "inline";

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        display: "flex",
        flexDirection: isInline ? "row" : "column",
        gap: 8,
        width: "100%",
        maxWidth: isInline ? 440 : 320,
      }}
    >
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@company.com"
        required
        style={{
          flex: 1,
          padding: "12px 16px",
          borderRadius: 8,
          border: "1px solid rgba(255, 255, 255, 0.12)",
          background: "rgba(255, 255, 255, 0.06)",
          color: "#f1f5f9",
          fontFamily: "var(--font-ui)",
          fontSize: 14,
          outline: "none",
          transition: "border-color 0.2s ease",
        }}
        onFocus={(e) => {
          e.currentTarget.style.borderColor = "rgba(20, 184, 166, 0.4)";
        }}
        onBlur={(e) => {
          e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.12)";
        }}
      />
      <button
        type="submit"
        disabled={status === "loading"}
        className="rooben-cta"
        style={{
          padding: "12px 24px",
          fontSize: 14,
          whiteSpace: "nowrap",
          opacity: status === "loading" ? 0.7 : 1,
        }}
      >
        {status === "loading" ? "Joining..." : "Join the Waitlist"}
      </button>
      {status === "error" && (
        <span style={{ color: "#f87171", fontSize: 12, fontFamily: "var(--font-ui)" }}>
          Something went wrong. Try again.
        </span>
      )}
    </form>
  );
}
