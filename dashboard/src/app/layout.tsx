import type { Metadata } from "next";
import { Sidebar } from "@/components/layout/Sidebar";
import { SetupProvider } from "@/lib/use-setup";
import { ConnectionProvider } from "@/lib/connection-context";
import { SetupGate } from "@/components/setup/SetupGate";
import "./globals.css";

export const metadata: Metadata = {
  title: "Rooben \u2014 Your taste is the product",
  description: "Turn plain English into verified, multi-agent work product. Budget-safe, transparent, and cross-domain.",
  icons: {
    icon: "/favicon.svg",
    apple: "/favicon.svg",
  },
  openGraph: {
    title: "Rooben \u2014 Your taste is the product",
    description: "Turn plain English into verified, multi-agent work product with cost control, verification scoring, and full transparency.",
    type: "website",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "Rooben \u2014 Your taste is the product" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Rooben \u2014 Your taste is the product",
    description: "Turn plain English into verified, multi-agent work product with cost control, verification scoring, and full transparency.",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body
        className="h-full antialiased"
        style={{
          backgroundColor: "var(--color-base)",
          color: "var(--color-text-primary)",
          fontFamily: "var(--font-ui)",
        }}
      >
        <SetupProvider>
          <ConnectionProvider>
            <SetupGate>
              <div className="flex h-full">
                <Sidebar />

                <div className="flex flex-1 flex-col overflow-hidden">
                  <main
                    className="flex-1 overflow-y-auto p-6 animate-fade-in"
                    style={{ backgroundColor: "var(--color-surface-1)" }}
                  >
                    {children}
                  </main>
                </div>
              </div>
            </SetupGate>
          </ConnectionProvider>
        </SetupProvider>
      </body>
    </html>
  );
}
