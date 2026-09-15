import Link from "next/link";
import { notFound } from "next/navigation";

import { PageHead } from "@/components/PageHead";
import { Stat } from "@/components/Stat";
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
  const bound = vars.filter((v) => v.role === "variable" && v.bind_path);
  const unbound = vars.filter((v) => v.role === "variable" && !v.bind_path);
  const auto = unbound.filter((v) => coveredBy(v.evidence).length > 0);
  const needsDecision = unbound
    .filter((v) => coveredBy(v.evidence).length === 0)
    .sort((a, b) => occurrences(b.occurrences) - occurrences(a.occurrences));

  const groups = [
    {
      title: "Vyžaduje rozhodnutí",
      note: "Hodnoty, které import sám nepozná ani nedopočítá. Vyberte, čemu odpovídají — nebo je označte jako fixní text či firemní konstantu.",
      rows: needsDecision,
      open: true,
      tone: "warn" as const,
    },
    {
      title: "Navázané proměnné",
      note: "Import je poznal podle popisku. Zkontrolujte, jestli ukazují tam, kam mají.",
      rows: bound,
      open: true,
      tone: "good" as const,
    },
    {
      title: "Vyřeší se automaticky",
      note: "Jiné zápisy údaje, který už navázaný je („50,0 kWp“ v tabulce, „50,0kWp“ ve větě). Přepíší se spolu s ním; procházet je nemusíte.",
      rows: auto,
      open: false,
      tone: "neutral" as const,
    },
    {
      title: "Generované pasáže",
      note: "Zeleně označený text. Vytvoří ho AI z dat projektu, ale až po vašem potvrzení.",
      rows: vars.filter((v) => v.role === "generated"),
      open: false,
      tone: "neutral" as const,
    },
    {
      title: "Zvýrazněné popisky",
      note: "Zvýrazněná je hlavička buňky, ne hodnota. Jako fixní text se přestanou podbarvovat.",
      rows: vars.filter((v) => v.role === "fixed"),
      open: false,
      tone: "neutral" as const,
    },
  ].filter((g) => g.rows.length > 0);

  return (
    <>
      <Link
        href="/sablony"
        className="mb-3 inline-flex items-center gap-1 text-xs"
        style={{ color: "var(--muted)" }}
      >
        ← Šablony
      </Link>

      <PageHead
        title={`${template.setCode} · ${template.docCode} — ${template.title}`}
        lead="Barva v šabloně je vodítko, ne rozhodnutí. Import ukazuje, co si myslí a proč; potvrzuje to vždycky člověk. Vaše opravy se použijí i u dalších šablon."
      >
        {template.status === "potvrzena" ? (
          <form action={reopenTemplate}>
            <input type="hidden" name="templateId" value={template.id} />
            <button className="btn" type="submit">
              Projít znovu
            </button>
          </form>
        ) : (
          <span className="pill pill-warn self-start">k potvrzení</span>
        )}
      </PageHead>

      <div className="mb-7 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat value={needsDecision.length} label="vyžaduje rozhodnutí" tone="warn" />
        <Stat value={bound.length} label="navázaných" tone="good" />
        <Stat value={auto.length} label="vyřeší se samo" />
        <Stat value={vars.filter((v) => v.role === "generated").length} label="generovaných pasáží" />
      </div>

      <form action={saveDecisions} className="space-y-5">
        <input type="hidden" name="templateId" value={template.id} />

        {groups.map((group) => (
          <details
            key={group.title}
            open={group.open}
            className="surface overflow-hidden [&[open]>summary_.chev]:rotate-90"
          >
            <summary className="surface-header cursor-pointer list-none">
              <div className="flex items-start gap-2.5">
                <svg
                  className="chev mt-1 transition-transform"
                  width="10"
                  height="10"
                  viewBox="0 0 10 10"
                  aria-hidden
                >
                  <path d="M3 1.5 7 5l-4 3.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
                </svg>
                <div>
                  <h2 className="text-sm font-semibold">{group.title}</h2>
                  <p className="mt-0.5 max-w-3xl text-xs font-normal" style={{ color: "var(--muted)" }}>
                    {group.note}
                  </p>
                </div>
              </div>
              <span
                className={
                  group.tone === "warn"
                    ? "pill pill-warn"
                    : group.tone === "good"
                      ? "pill pill-good"
                      : "pill pill-neutral"
                }
              >
                {group.rows.length}
              </span>
            </summary>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px]">
                <thead>
                  <tr>
                    <th className="th">Hodnota v šabloně</th>
                    <th className="th">Popisek</th>
                    <th className="th">Role</th>
                    <th className="th">Údaj v projektu</th>
                    <th className="th text-right">Výskytů</th>
                  </tr>
                </thead>
                <tbody>
                  {group.rows.map((row) => {
                    const values = samples(row.sample_values);
                    return (
                      <tr key={row.id} className="row">
                        <td className="td max-w-[24rem]">
                          <span className="literal">
                            {values[0]?.slice(0, 110) || "—"}
                          </span>
                          {values.length > 1 && (
                            <span className="ml-1.5 text-xs" style={{ color: "var(--faint)" }}>
                              +{values.length - 1} jiný zápis
                            </span>
                          )}
                        </td>
                        <td className="td text-xs" style={{ color: "var(--muted)" }}>
                          {row.label ?? "—"}
                        </td>
                        <td className="td">
                          <select
                            name={`role.${row.id}`}
                            defaultValue={row.role}
                            className="field field-sm"
                          >
                            {Object.entries(ROLE_LABELS).map(([v, l]) => (
                              <option key={v} value={v}>
                                {l}
                              </option>
                            ))}
                          </select>
                          <label
                            className="mt-1.5 flex items-center gap-1.5 text-[11px]"
                            style={{ color: "var(--muted)" }}
                          >
                            <input
                              type="checkbox"
                              name={`const.${row.id}`}
                              defaultChecked={row.is_company_constant}
                            />
                            firemní konstanta
                          </label>
                        </td>
                        <td className="td">
                          <select
                            name={`bind.${row.id}`}
                            defaultValue={row.bind_path ?? ""}
                            className="field field-sm"
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
                        <td className="td text-right text-xs" style={{ color: "var(--muted)" }}>
                          {occurrences(row.occurrences)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </details>
        ))}

        <div
          className="sticky bottom-0 -mx-5 flex flex-wrap items-center gap-3 border-t bg-white/95 px-5 py-3 backdrop-blur md:-mx-8 md:px-8"
          style={{ borderColor: "var(--line)" }}
        >
          <button type="submit" className="btn btn-primary">
            Potvrdit šablonu
          </button>
          <span className="text-xs" style={{ color: "var(--muted)" }}>
            Nenavázané proměnné zůstanou v dokumentu zvýrazněné, aby je nešlo
            splést s platným údajem.
          </span>
        </div>
      </form>
    </>
  );
}
