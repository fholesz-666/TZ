import Link from "next/link";

export default function NotFound() {
  return (
    <div className="surface px-6 py-14 text-center">
      <h1 className="text-lg font-semibold">Tady nic není</h1>
      <p className="mt-1.5 text-sm" style={{ color: "var(--muted)" }}>
        Stránka neexistuje, nebo byl záznam smazán.
      </p>
      <Link href="/" className="btn mt-5">
        Zpět na projekty
      </Link>
    </div>
  );
}
