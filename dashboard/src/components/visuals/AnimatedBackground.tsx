"use client";

interface AnimatedBackgroundProps {
  variant?: "hero" | "subtle" | "card";
  children?: React.ReactNode;
  className?: string;
}

export function AnimatedBackground({
  variant = "hero",
  children,
  className = "",
}: AnimatedBackgroundProps) {
  if (variant === "hero") {
    return (
      <div className={`rooben-hero-bg ${className}`} style={{ minHeight: "100vh" }}>
        {children}
      </div>
    );
  }

  if (variant === "subtle") {
    return (
      <div
        className={className}
        style={{
          position: "relative",
          background:
            "linear-gradient(135deg, var(--color-surface-1) 0%, var(--color-surface-2) 50%, var(--color-surface-1) 100%)",
          backgroundSize: "200% 200%",
          animation: "gradient-shift 20s ease infinite",
        }}
      >
        {children}
      </div>
    );
  }

  // card variant
  return (
    <div
      className={className}
      style={{
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at 50% 50%, rgba(20, 184, 166, 0.06) 0%, transparent 70%)",
          pointerEvents: "none",
        }}
      />
      {children}
    </div>
  );
}
