import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { themeScript } from "@/lib/theme-script";
import "./globals.css";

// Self-hosted at build time by next/font, so the CSP needs no external font origin.
const sans = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });

export const metadata: Metadata = { title: "MME OS", description: "MME internal Business OS" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // data-theme is set by themeScript before hydration, so React must not warn about it.
    <html lang="en" className={sans.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
