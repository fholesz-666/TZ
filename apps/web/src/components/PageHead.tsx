/** Hlavička stránky: co to je, k čemu to je, a co se s tím dá udělat. */
export function PageHead({
  title,
  lead,
  children,
}: {
  title: string;
  lead?: string;
  children?: React.ReactNode;
}) {
  return (
    <header className="mb-7 flex flex-wrap items-start justify-between gap-4">
      <div className="max-w-2xl">
        <h1 className="text-[22px] font-semibold tracking-tight">{title}</h1>
        {lead && (
          <p className="mt-1.5 text-sm leading-relaxed" style={{ color: "var(--muted)" }}>
            {lead}
          </p>
        )}
      </div>
      {children && <div className="flex gap-2">{children}</div>}
    </header>
  );
}
