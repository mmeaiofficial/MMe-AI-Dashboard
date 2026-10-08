import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "MME OS", description: "MME internal Business OS" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
