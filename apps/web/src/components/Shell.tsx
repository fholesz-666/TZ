"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * Rám aplikace. Na širokém displeji svislá navigace (bod 3 zadání:
 * na desktopu víc informací naráz), na mobilu se sbalí nahoru.
 */

const NAV = [
  { href: "/", label: "Projekty", icon: FolderIcon },
  { href: "/sablony", label: "Šablony", icon: LayersIcon },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <div className="min-h-dvh md:grid md:grid-cols-[232px_1fr]">
      <aside className="border-b bg-white md:sticky md:top-0 md:h-dvh md:border-b-0 md:border-r"
             style={{ borderColor: "var(--line)" }}>
        <div className="flex items-center gap-2.5 px-5 py-4">
          <Mark />
          <div className="leading-tight">
            <div className="text-sm font-semibold">FVE dokumentace</div>
            <div className="text-[11px]" style={{ color: "var(--faint)" }}>
              projektová dokumentace
            </div>
          </div>
        </div>
        <nav className="flex gap-1 px-3 pb-3 md:flex-col">
          {NAV.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              data-active={isActive(href)}
              className="nav-link"
            >
              <Icon />
              {label}
            </Link>
          ))}
        </nav>
      </aside>

      <div className="min-w-0">
        <div className="mx-auto max-w-5xl px-5 py-7 md:px-8 md:py-9">
          {children}
        </div>
      </div>
    </div>
  );
}

function Mark() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden>
      <rect width="28" height="28" rx="7" fill="var(--accent)" />
      <path
        d="M7 18.5 14 7l7 11.5H7Z"
        fill="none"
        stroke="#fff"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path d="M10.2 15h7.6" stroke="#fff" strokeWidth="1.4" />
    </svg>
  );
}

function FolderIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M1.8 4.2c0-.66.54-1.2 1.2-1.2h2.7l1.4 1.6h5.9c.66 0 1.2.54 1.2 1.2v6c0 .66-.54 1.2-1.2 1.2H3c-.66 0-1.2-.54-1.2-1.2V4.2Z"
        stroke="currentColor"
        strokeWidth="1.3"
      />
    </svg>
  );
}

function LayersIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M8 1.8 14.5 5 8 8.2 1.5 5 8 1.8Z"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinejoin="round"
      />
      <path
        d="M2.4 8.2 8 11l5.6-2.8M2.4 11.3 8 14.1l5.6-2.8"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinejoin="round"
      />
    </svg>
  );
}
