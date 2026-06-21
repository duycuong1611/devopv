import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RelayOps",
  description: "GitHub webhook monitor and controlled deployment automation",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
