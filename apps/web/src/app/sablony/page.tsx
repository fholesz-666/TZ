import Link from "next/link";

import { db, listSets } from "@/lib/db";
import { engineHealthy } from "@/lib/engine";

import { deleteTemplate, ensureDefaultSets, uploadTemplate } from "./actions";

export const dynamic = "force-dynamic";

export default async function TemplatesPage() {
  await ensureDefaultSets();
  const [sets, templates, engineUp] = await Promise.all([
    listSets(),
    db
      .selectFrom("templates")
      .innerJoin("template_sets", "template_sets.id", "templates.set_id")
      .select([
        "templates.id as id",
        "templates.doc_code as docCode",
        "templates.title as title",
        "templates.status as status",
        "templates.manifest as manifest",
        "template_sets.code as setCode",
      ])
      .orderBy("template_sets.code")
      .orderBy("templates.doc_code")
      .execute(),
    engineHealthy(),
  ]);

  return (
    <div className="space-y-7">
      <div>
        <h1 className="text-xl font-semibold">Šablony</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          Šablona se nahraje tak, jak je — i s razítkem a barevným značením.
          Originál se neupravuje; import z něj jen přečte, co je proměnné, co
          generované a co fixní, a vy to potvrdíte.
        </p>
      </div>

      {!engineUp && (
        <div className="card border-bad/30 bg-[#fdf3f2] p-3 text-sm text-bad">
          Dokumentová služba neběží. Bez ní nejde šablonu rozebrat — spusťte{" "}
          <code className="font-mono text-xs">uvicorn app.main:app --port 8100</code>{" "}
          v <code className="font-mono text-xs">packages/docx-engine</code>.
        </div>
      )}

      <section className="card p-5">
        <h2 className="text-sm font-semibold">Nahrát šablonu</h2>
        <form action={uploadTemplate} className="mt-4 grid gap-4 sm:grid-cols-4">
          <div>
            <label className="label" htmlFor="setId">
              Sada
            </label>
            <select id="setId" name="setId" className="input mt-1" required>
              {sets.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} — {s.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="docCode">
              Označení dokumentu
            </label>
            <input
              id="docCode"
              name="docCode"
              className="input mt-1"
              placeholder="D.2.2"
              required
            />
          </div>
          <div>
            <label className="label" htmlFor="title">
              Název
            </label>
            <input
              id="title"
              name="title"
              className="input mt-1"
              placeholder="Technická zpráva FVE"
            />
          </div>
          <div>
            <label className="label" htmlFor="file">
              Soubor .docx
            </label>
            <input
              id="file"
              name="file"
              type="file"
              accept=".docx"
              className="input mt-1 py-1"
              required
            />
          </div>
          <div className="sm:col-span-4">
            <button type="submit" className="btn btn-primary">
              Nahrát a rozebrat
            </button>
          </div>
        </form>
      </section>

      <section className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#f2f4f7] text-left text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="px-4 py-2 font-medium">Sada</th>
              <th className="px-4 py-2 font-medium">Dokument</th>
              <th className="px-4 py-2 font-medium">Název</th>
              <th className="px-4 py-2 text-right font-medium">Proměnné</th>
              <th className="px-4 py-2 text-right font-medium">Generované</th>
              <th className="px-4 py-2 font-medium">Stav</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {templates.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-muted">
                  Zatím tu není žádná šablona.
                </td>
              </tr>
            )}
            {templates.map((t) => {
              const stats = (t.manifest as { stats?: Record<string, number> })
                .stats;
              return (
                <tr key={t.id} className="border-t border-line">
                  <td className="px-4 py-2 font-mono text-xs">{t.setCode}</td>
                  <td className="px-4 py-2 font-mono text-xs">{t.docCode}</td>
                  <td className="px-4 py-2">
                    <Link
                      href={`/sablony/${t.id}`}
                      className="text-accent hover:underline"
                    >
                      {t.title}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {stats?.variables ?? 0}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {stats?.generated_segments ?? 0}
                  </td>
                  <td className="px-4 py-2">
                    {t.status === "potvrzena" ? (
                      <span className="badge bg-[#e8f5ef] text-good">
                        potvrzená
                      </span>
                    ) : (
                      <span className="badge bg-[#fdf6e7] text-warn">
                        k potvrzení
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <form action={deleteTemplate}>
                      <input type="hidden" name="id" value={t.id} />
                      <button className="btn text-xs" type="submit">
                        Odebrat
                      </button>
                    </form>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </div>
  );
}
