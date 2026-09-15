import Link from "next/link";

import { PageHead } from "@/components/PageHead";
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
        "template_sets.name as setName",
      ])
      .orderBy("template_sets.code")
      .orderBy("templates.doc_code")
      .execute(),
    engineHealthy(),
  ]);

  const bySet = sets.map((s) => ({
    ...s,
    templates: templates.filter((t) => t.setCode === s.code),
  }));

  return (
    <>
      <PageHead
        title="Šablony"
        lead="Šablona se nahraje tak, jak je — i s razítkem a barevným značením. Originál se neupravuje; import z něj jen přečte, co je proměnné, co generované a co fixní, a vy to potvrdíte."
      />

      {!engineUp && (
        <div className="note note-bad mb-6">
          <strong className="font-semibold">Dokumentová služba neběží.</strong>{" "}
          Bez ní nejde šablonu rozebrat. Spusťte v adresáři{" "}
          <span className="literal">packages/docx-engine</span> příkaz{" "}
          <span className="literal">uvicorn app.main:app --port 8100</span>.
        </div>
      )}

      <section className="surface mb-7">
        <div className="surface-header">
          <div>
            <h2 className="text-sm font-semibold">Nahrát šablonu</h2>
            <p className="mt-0.5 text-xs" style={{ color: "var(--muted)" }}>
              Soubor .docx se uloží beze změny a pošle k rozboru.
            </p>
          </div>
        </div>
        <form action={uploadTemplate} className="grid gap-4 p-5 sm:grid-cols-12">
          <div className="sm:col-span-3">
            <label className="label" htmlFor="setId">
              Sada
            </label>
            <select id="setId" name="setId" className="field" required>
              {sets.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} — {s.name}
                </option>
              ))}
            </select>
          </div>
          <div className="sm:col-span-2">
            <label className="label" htmlFor="docCode">
              Dokument
            </label>
            <input
              id="docCode"
              name="docCode"
              className="field"
              placeholder="D.2.2"
              required
            />
          </div>
          <div className="sm:col-span-4">
            <label className="label" htmlFor="title">
              Název
            </label>
            <input
              id="title"
              name="title"
              className="field"
              placeholder="Technická zpráva FVE"
            />
          </div>
          <div className="sm:col-span-3">
            <label className="label" htmlFor="file">
              Soubor
            </label>
            <input
              id="file"
              name="file"
              type="file"
              accept=".docx"
              className="field py-1.5 text-xs file:mr-3 file:rounded file:border-0 file:bg-[#eef0f3] file:px-2 file:py-1 file:text-xs"
              required
            />
          </div>
          <div className="sm:col-span-12">
            <button type="submit" className="btn btn-primary" disabled={!engineUp}>
              Nahrát a rozebrat
            </button>
          </div>
        </form>
      </section>

      <div className="space-y-5">
        {bySet.map((set) => (
          <section key={set.id} className="surface overflow-hidden">
            <div className="surface-header">
              <div>
                <h2 className="text-sm font-semibold">
                  <span className="literal mr-2">{set.code}</span>
                  {set.name}
                </h2>
                <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                  {set.company}
                </p>
              </div>
              <span className="pill pill-neutral">
                {set.templates.length}{" "}
                {set.templates.length === 1 ? "šablona" : "šablon"}
              </span>
            </div>

            {set.templates.length === 0 ? (
              <p className="px-5 py-6 text-sm" style={{ color: "var(--faint)" }}>
                Zatím žádná šablona.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px]">
                  <thead>
                    <tr>
                      <th className="th">Dokument</th>
                      <th className="th">Název</th>
                      <th className="th text-right">Proměnné</th>
                      <th className="th text-right">Generované</th>
                      <th className="th">Stav</th>
                      <th className="th" />
                    </tr>
                  </thead>
                  <tbody>
                    {set.templates.map((t) => {
                      const stats = (
                        t.manifest as { stats?: Record<string, number> }
                      ).stats;
                      return (
                        <tr key={t.id} className="row">
                          <td className="td">
                            <span className="literal">{t.docCode}</span>
                          </td>
                          <td className="td">
                            <Link
                              href={`/sablony/${t.id}`}
                              className="font-medium hover:underline"
                              style={{ color: "var(--accent)" }}
                            >
                              {t.title}
                            </Link>
                          </td>
                          <td className="td text-right">{stats?.variables ?? 0}</td>
                          <td className="td text-right">
                            {stats?.generated_segments ?? 0}
                          </td>
                          <td className="td">
                            {t.status === "potvrzena" ? (
                              <span className="pill pill-good">potvrzená</span>
                            ) : (
                              <span className="pill pill-warn">k potvrzení</span>
                            )}
                          </td>
                          <td className="td text-right">
                            <form action={deleteTemplate}>
                              <input type="hidden" name="id" value={t.id} />
                              <button className="btn btn-sm" type="submit">
                                Odebrat
                              </button>
                            </form>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        ))}
      </div>
    </>
  );
}
