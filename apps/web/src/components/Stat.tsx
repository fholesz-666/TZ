/** Jedno číslo s popiskem. Používá se v přehledech nad tabulkami. */
export function Stat({
  value,
  label,
  tone = "neutral",
}: {
  value: React.ReactNode;
  label: string;
  tone?: "neutral" | "good" | "warn";
}) {
  const color =
    tone === "good" ? "var(--good)" : tone === "warn" ? "var(--warn)" : "var(--ink)";
  return (
    <div className="surface px-4 py-3">
      <div className="tabular text-xl font-semibold" style={{ color }}>
        {value}
      </div>
      <div className="mt-0.5 text-xs" style={{ color: "var(--muted)" }}>
        {label}
      </div>
    </div>
  );
}
