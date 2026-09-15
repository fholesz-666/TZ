import Link from "next/link";
import { notFound } from "next/navigation";

import { db } from "@/lib/db";
import { modelPaths } from "@/lib/model-paths";

import { reopenTemplate, saveDecisions } from "./actions";

export const dynamic = "force-dynamic";

const ROLE_LABELS: Record<string, string> = {
  variable: "Proměnná",
  generated: "Generovaný text",
  fixed: "Fixní text",
};

function samples(value: unknown): string[] {
  return Array.isArray(value) ? (value as string[]) : [];
}

function occurrences(value: unknown): number {
  return Array.isArray(value) ? value.length : 0;
}

/** Úsek, který umí přepsat slovník sám, nepotřebuje rozhodnutí. */
function coveredBy(evidence: unknown): string[] {
  const list = (evidence as { covered_by?: unknown })?.covered_by;
  return Array.isArray(list) ? (list as string[]) : [];
}

export default async function TemplateWizard({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const template = await db
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
    .where("templates.id", "=", id)
    .executeTakeFirst();
  if (!template) notFound();

  const vars = await db
    .selectFrom("template_variables")
    .selectAll()
    .where("template_id", "=", id)
    .orderBy("role")
    .orderBy("key")
    .execute();

  const paths = modelPaths();
  const stats = (template.manifest as { stats?: Record<string, number> }).stats;

  const unbound = vars.filter((v) => v.role === "variable" && !v.bind_path);
  const auto = unbound.filter((v) => coveredBy(v.evidence).length > 0);
  const needsDecision = unbound
    .filter((v) => coveredBy(v.evidence).length === 0)
    .sort((a, b) => occurrences(b.occurrences) - occurrences(a.occurrences));

  const groups = [
    {
      title: "Navázané proměnné",
      note: "Import je poznal podle popisku. Zkontrolujte, jestli ukazují tam, kam mají.",
      rows: vars.filter((v) => v.role === "variable" && v.bind_path),
      collapsed: false,
    },
    {
      title: "Vyžaduje rozhodnutí",
      note: "Hodnoty, které import sám nepozná ani nedopočítá. Vyberte, čemu odpovídají — nebo je označte jako fixní text či firemní konstantu.",
      rows: needsDecision,
      collapsed: false,
    },
    {
      title: "Vyřeší se automaticky",
      note: "Jiné zápisy údaje, který už navázaný je („50,0 kWp“ v tabulce, „50,0kWp“ ve větě). Přepíší se spolu s ním; procházet je nemusíte.",
      rows: auto,
      collapsed: true,
    },
    {
      title: "Generované pasáže",
      note: "Zeleně označený text. Vytvoří ho AI z dat projektu, ale až po vašem potvrzení.",
      rows: vars.filter((v) => v.role === "generated"),
      collapsed: false,
    },
    {
      title: "Zvýrazněné popisky",
      note: "Zvýrazněná je hlavička buňky, ne hodnota. Jako fixní text se přestanou podbarvovat.",
      rows: vars.filter((v) => v.role === "fixed"),
      collapsed: false,
    },
  ].filter((g) => g.rows.length > 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/sablony" className="text-xs text-muted hover:text-ink">
            ← Šablony
          </Link>
          <h1 className="mt-1 text-xl font-semibold">
            {template.setCode} · {template.docCode} — {template.title}
          </h1>
          <p className="mt-1 text-sm text-muted">
            {stats?.variables ?? 0} proměnných ve {stats?.variable_occurrences ?? 0}{" "}
            místech, {stats?.generated_segments ?? 0} generovaných pasáží,{" "}
            {stats?.suspect_labels ?? 0} zvýrazněných popisků.
          </p>
        </div>
        {template.status === "potvrzena" ? (
          <form action={reopenTemplate}>
            <input type="hidden" name="templateId" value={template.id} />
            <button className="btn" type="submit">
              Projít znovu
            </button>
          </form>
        ) : null}
      </div>

      <div className="card bg-[#f6f9ff] p-4 text-sm">
        <p className="text-ink">
          Barva v šabloně je vodítko, ne rozhodnutí. Import ukazuje, co si
          myslí a proč — potvrzuje to vždycky člověk. Vaše opravy se použijí
          i u dalších šablon.
        </p>
      </div>

      <form action={saveDecisions} className="space-y-6">
        <input type="hidden" name="templateId" value={template.id} />

        {groups.map((group) => (
          <details
            key={group.title}
            open={!group.collapsed}
            className="card overflow-hidden"
          >
            <summary className="cursor-pointer border-b border-line px-4 py-3">
              <span className="text-sm font-semibold">
                {group.title}{" "}
                <span className="font-normal text-muted">
                  ({group.rows.length})
                </span>
              </span>
              <p className="mt-0.5 text-xs font-normal text-muted">
                {group.note}
              </p>
            </summary>
            <table className="w-full text-sm">
              <thead className="bg-[#fafbfc] text-left text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-4 py-2 font-medium">Hodnota v šabloně</th>
                  <th className="px-4 py-2 font-medium">Popisek</th>
                  <th className="px-4 py-2 font-medium">Role</th>
                  <th className="px-4 py-2 font-medium">Údaj v projektu</th>
                  <th className="px-4 py-2 text-right font-medium">Výskytů</th>
                </tr>
              </thead>
              <tbody>
                {group.rows.map((row) => {
                  const values = samples(row.sample_values);
                  return (
                    <tr key={row.id} className="border-t border-line align-top">
                      <td className="max-w-[22rem] px-4 py-2">
                        <span className="font-mono text-xs text-ink">
                          {values[0]?.slice(0, 120) || "—"}
                        </span>
                        {values.length > 1 && (
                          <span className="ml-1 text-xs text-muted">
                            +{values.length - 1} další zápis
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-xs text-muted">
                        {row.label ?? "—"}
                      </td>
                      <td className="px-4 py-2">
                        <select
                          name={`role.${row.id}`}
                          defaultValue={row.role}
                          className="input py-1 text-xs"
                        >
                          {Object.entries(ROLE_LABELS).map(([v, l]) => (
                            <option key={v} value={v}>
                              {l}
                            </option>
                          ))}
                        </select>
                        <label className="mt-1 flex items-center gap-1 text-[11px] text-muted">
                          <input
                            type="checkbox"
                            name={`const.${row.id}`}
                            defaultChecked={row.is_company_constant}
                          />
                          firemní konstanta
                        </label>
                      </td>
                      <td className="px-4 py-2">
                        <select
                          name={`bind.${row.id}`}
                          defaultValue={row.bind_path ?? ""}
                          className="input py-1 text-xs"
                        >
                          <option value="">— nenavázáno —</option>
                          {paths.map((p) => (
                            <option key={p.path} value={p.path}>
                              {p.path}
                              {p.derived ? " (odvozené)" : ""}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-xs text-muted">
                        {occurrences(row.occurrences)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </details>
        ))}

        <div className="flex items-center gap-3">
          <button type="submit" className="btn btn-primary">
            Potvrdit šablonu
          </button>
          <span className="text-xs text-muted">
            Nenavázané proměnné zůstanou v dokumentu zvýrazněné, aby je nešlo
            splést s platným údajem.
          </span>
        </div>
      </form>
    </div>
  );
}
