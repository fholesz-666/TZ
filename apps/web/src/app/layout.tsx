import type { Metadata, Viewport } from "next";

import { Shell } from "@/components/Shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "FVE dokumentace",
  description: "Tvorba projektové dokumentace fotovoltaických elektráren",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#1d4ed8",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="cs">
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
