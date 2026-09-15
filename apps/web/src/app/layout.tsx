import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "FVE dokumentace",
  description: "Tvorba projektové dokumentace fotovoltaických elektráren",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="cs">
      <body>
        <header className="border-b border-line bg-white">
          <div className="mx-auto flex max-w-6xl items-center gap-6 px-5 py-3">
            <Link href="/" className="text-sm font-semibold tracking-tight">
              FVE dokumentace
            </Link>
            <nav className="flex gap-4 text-sm text-muted">
              <Link href="/" className="hover:text-ink">
                Projekty
              </Link>
              <Link href="/sablony" className="hover:text-ink">
                Šablony
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-5 py-7">{children}</main>
      </body>
    </html>
  );
}
