import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { CommandPalette } from "@/components/layout/CommandPalette";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar, type SystemStatus } from "@/components/layout/Topbar";
import { api } from "@/lib/api";
import "./globals.css";

const sans = Geist({ variable: "--font-sans", subsets: ["latin"] });
const mono = Geist_Mono({ variable: "--font-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ChurnGuard — Customer churn early-warning",
  description:
    "Identify customers likely to churn, understand why, verify the evidence, and recommend economically justified interventions.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // The shell reports the service's real state. If the API is down, every page
  // still renders and says so, rather than the whole app failing to load.
  let status: SystemStatus;
  let analysisTime: string | undefined;
  try {
    const health = await api.health();
    analysisTime = health.analysis_time;
    status = {
      ok: true,
      customers: health.active_customers,
      analysisTime: health.analysis_time,
    };
  } catch (error) {
    status = { ok: false, message: error instanceof Error ? error.message : "unreachable" };
  }

  return (
    <html lang="en">
      <body className={`${sans.variable} ${mono.variable} antialiased`}>
        <div className="flex min-h-screen">
          <Sidebar analysisTime={analysisTime} />
          <div className="flex min-w-0 flex-1 flex-col">
            <Topbar status={status} />
            <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-6">
              {children}
            </main>
          </div>
        </div>
        <CommandPalette />
      </body>
    </html>
  );
}
