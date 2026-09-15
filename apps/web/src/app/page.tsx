import Link from "next/link";

import { PageHead } from "@/components/PageHead";
import { Stat } from "@/components/Stat";
import { db, ensureWorkspace } from "@/lib/db";

export const dynamic = "force-dynamic";

const STATUS_LABELS: Record<string, string> = {
  rozpracovany: "rozpracovaný",
  ke_kontrole: "ke kontrole",
  schvaleny: "schválený",
  realizovany: "realizovaný",
  archivovany: "archivovaný",
};

export default async function Home() {
  await ensureWorkspace();
  const [projects, templates] = await Promise.all([
    db
      .selectFrom("projects")
      .select(["id", "order_number", "name", "status", "updated_at", "data"])
      .where("archived_at", "is", null)
      .orderBy("updated_at", "desc")
      .execute(),
    db.selectFrom("templates").select(["id", "status"]).execute(),
  ]);

  const confirmed = templates.filter((t) => t.status === "potvrzena").length;

  return (
    <>
      <PageHead
        title="Projekty"
        lead="Projekt se založí, uloží a kdykoliv upraví. Dokumentace se z něj vygeneruje znovu, původní verze zůstane."
      >
        <button className="btn btn-primary" disabled title="Přijde v dalším kroku">
          Nový projekt
        </button>
      </PageHead>

      <div className="mb-7 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Stat value={projects.length} label="rozpracovaných projektů" />
        <Stat value={templates.length} label="nahraných šablon" />
        <Stat
          value={confirmed}
          label="potvrzených šablon"
          tone={confirmed > 0 ? "good" : "warn"}
        />
      </div>

      {projects.length === 0 ? (
        <section className="surface px-6 py-14 text-center">
          <div
            className="mx-auto flex h-11 w-11 items-center justify-center rounded-xl"
            style={{ background: "var(--accent-soft)" }}
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
              <path
                d="M4 15.5 10 4l6 11.5H4Z"
                stroke="var(--accent)"
                strokeWidth="1.6"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <h2 className="mt-4 text-base font-semibold">Zatím tu není žádný projekt</h2>
          <p
            className="mx-auto mt-1.5 max-w-md text-sm leading-relaxed"
            style={{ color: "var(--muted)" }}
          >
            {confirmed === 0
              ? "Nejdřív nahrajte šablonu a projděte průvodce importem. Bez potvrzené šablony není z čeho dokumentaci vygenerovat."
              : `Šablony máte připravené (${confirmed} potvrzených). Zakládání projektu přijde v dalším kroku.`}
          </p>
          <Link href="/sablony" className="btn btn-primary mt-5">
            Přejít na šablony
          </Link>
        </section>
      ) : (
        <section className="surface overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px]">
              <thead>
                <tr>
                  <th className="th">Zakázka</th>
                  <th className="th">Název</th>
                  <th className="th text-right">Výkon</th>
                  <th className="th">Stav</th>
                  <th className="th">Změněno</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((p) => {
                  const kwp = (
                    (p.data as { energy?: { p_dc_kwp?: number } }).energy ?? {}
                  ).p_dc_kwp;
                  return (
                    <tr key={p.id} className="row">
                      <td className="td">
                        <span className="literal">{p.order_number}</span>
                      </td>
                      <td className="td font-medium">{p.name}</td>
                      <td className="td text-right">
                        {kwp ? `${String(kwp).replace(".", ",")} kWp` : "—"}
                      </td>
                      <td className="td">
                        <span className="pill pill-neutral">
                          {STATUS_LABELS[p.status] ?? p.status}
                        </span>
                      </td>
                      <td className="td text-xs" style={{ color: "var(--muted)" }}>
                        {new Date(p.updated_at).toLocaleDateString("cs-CZ")}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}
