import Link from "next/link";

import { db, ensureWorkspace } from "@/lib/db";

export const dynamic = "force-dynamic";

export default async function Home() {
  await ensureWorkspace();
  const [projects, templates] = await Promise.all([
    db
      .selectFrom("projects")
      .select(["id", "order_number", "name", "status", "updated_at"])
      .where("archived_at", "is", null)
      .orderBy("updated_at", "desc")
      .execute(),
    db
      .selectFrom("templates")
      .select(["id", "status"])
      .execute(),
  ]);

  const confirmed = templates.filter((t) => t.status === "potvrzena").length;

  return (
    <div className="space-y-7">
      <div>
        <h1 className="text-xl font-semibold">Projekty</h1>
        <p className="mt-1 text-sm text-muted">
          Projekt se založí, uloží a kdykoliv upraví. Dokumentace se z něj
          vygeneruje znovu, původní verze zůstane.
        </p>
      </div>

      {projects.length === 0 && (
        <div className="card p-8 text-center">
          <p className="text-sm text-muted">Zatím tu není žádný projekt.</p>
          <p className="mt-2 text-sm text-muted">
            {confirmed === 0
              ? "Nejdřív je potřeba nahrát a potvrdit alespoň jednu šablonu."
              : `Potvrzených šablon: ${confirmed}.`}
          </p>
          <Link href="/sablony" className="btn btn-primary mt-4">
            Přejít na šablony
          </Link>
        </div>
      )}

      {projects.length > 0 && (
        <section className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#f2f4f7] text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-2 font-medium">Zakázka</th>
                <th className="px-4 py-2 font-medium">Název</th>
                <th className="px-4 py-2 font-medium">Stav</th>
                <th className="px-4 py-2 font-medium">Změněno</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((p) => (
                <tr key={p.id} className="border-t border-line">
                  <td className="px-4 py-2 font-mono text-xs">
                    {p.order_number}
                  </td>
                  <td className="px-4 py-2">{p.name}</td>
                  <td className="px-4 py-2 text-muted">{p.status}</td>
                  <td className="px-4 py-2 text-muted">
                    {new Date(p.updated_at).toLocaleDateString("cs-CZ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
