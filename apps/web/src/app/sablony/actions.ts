"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { db, ensureWorkspace } from "@/lib/db";
import { parseTemplate } from "@/lib/engine";
import { hashOf, keyFor, put } from "@/lib/storage";

/** Sady, se kterými se začíná. Další si uživatel přidá sám. */
const DEFAULT_SETS = [
  { code: "V1", name: "JABLONEC", company: "ENERG-SERVIS a.s." },
  { code: "V2", name: "UNIVERZÁL", company: "Univerzální sada" },
  { code: "V3", name: "SIMPLY", company: "SIMPLY fotovoltaika s.r.o." },
];

export async function ensureDefaultSets() {
  const user = await ensureWorkspace();
  for (const s of DEFAULT_SETS) {
    let company = await db
      .selectFrom("companies")
      .selectAll()
      .where("owner_id", "=", user.id)
      .where("name", "=", s.company)
      .executeTakeFirst();
    if (!company) {
      company = await db
        .insertInto("companies")
        .values({ owner_id: user.id, name: s.company })
        .returningAll()
        .executeTakeFirstOrThrow();
    }
    const exists = await db
      .selectFrom("template_sets")
      .select("id")
      .where("company_id", "=", company.id)
      .where("code", "=", s.code)
      .executeTakeFirst();
    if (!exists) {
      await db
        .insertInto("template_sets")
        .values({ company_id: company.id, code: s.code, name: s.name })
        .execute();
    }
  }
}

/**
 * Nahrání šablony: soubor se uloží beze změny, pošle se dokumentové
 * službě k rozboru a z jejího manifestu se založí kandidáti na proměnné.
 * Nic se nepotvrzuje automaticky – od toho je průvodce importem.
 */
export async function uploadTemplate(formData: FormData) {
  const setId = String(formData.get("setId") ?? "");
  const docCode = String(formData.get("docCode") ?? "").trim();
  const title = String(formData.get("title") ?? "").trim();
  const file = formData.get("file");

  if (!setId || !docCode || !(file instanceof File) || file.size === 0) {
    throw new Error("Vyberte sadu, zadejte označení dokumentu a soubor .docx.");
  }
  if (!file.name.toLowerCase().endsWith(".docx")) {
    throw new Error("Šablona musí být soubor .docx.");
  }

  const bytes = Buffer.from(await file.arrayBuffer());
  const manifest = await parseTemplate(file.name, bytes);
  const hash = hashOf(bytes);
  const key = keyFor(["templates", setId, `${docCode}-${hash}.docx`]);
  await put(key, bytes);

  const template = await db
    .insertInto("templates")
    .values({
      set_id: setId,
      doc_code: docCode,
      title: title || file.name.replace(/\.docx$/i, ""),
      file_key: key,
      file_hash: hash,
      manifest: manifest as unknown as Record<string, unknown>,
      status: "k_potvrzeni",
    })
    .onConflict((oc) =>
      oc.columns(["set_id", "doc_code"]).doUpdateSet({
        title: title || file.name.replace(/\.docx$/i, ""),
        file_key: key,
        file_hash: hash,
        manifest: manifest as unknown as Record<string, unknown>,
        status: "k_potvrzeni",
        updated_at: new Date(),
      }),
    )
    .returningAll()
    .executeTakeFirstOrThrow();

  await db
    .deleteFrom("template_variables")
    .where("template_id", "=", template.id)
    .execute();

  const rows = manifest.variables.map((v) => ({
    template_id: template.id,
    key: v.key,
    label: v.label,
    role: "variable",
    bind_path: v.mapped ? v.key : null,
    data_type: "text",
    confirmed: false,
    // Kolik různých zápisů téže hodnoty se v šabloně našlo – vodítko
    // pro uživatele, ne rozhodnutí.
    evidence: {
      occurrences: v.occurrences.length,
      distinct_values: v.sample_values.length,
      // Klíče, jejichž hodnotu umí slovník v tomhle úseku přepsat sám.
      // Když je seznam neprázdný, průvodce se na úsek nemusí ptát.
      covered_by: v.covered_by ?? [],
    },
    confidence: v.mapped ? 0.8 : 0.2,
    occurrences: JSON.stringify(v.occurrences),
    sample_values: JSON.stringify(v.sample_values),
  }));

  // Zvýrazněné popisky nejsou proměnné – uloží se rovnou jako fixní text,
  // aby je průvodce nabídl k potvrzení a víc se nepodbarvovaly.
  manifest.suspect_labels.forEach((s, i) => {
    rows.push({
      template_id: template.id,
      key: `popisek.${i}`,
      label: s.text,
      role: "fixed",
      bind_path: null,
      data_type: "text",
      confirmed: false,
      evidence: { occurrences: 1, distinct_values: 1, covered_by: [] },
      confidence: 0.9,
      occurrences: JSON.stringify([s]),
      sample_values: JSON.stringify([s.text]),
    });
  });

  manifest.generated_segments.forEach((g, i) => {
    rows.push({
      template_id: template.id,
      key: `generovany.${i}`,
      label: null,
      role: "generated",
      bind_path: null,
      data_type: "text",
      confirmed: false,
      evidence: { occurrences: 1, distinct_values: 1, covered_by: [] },
      confidence: 0.9,
      occurrences: JSON.stringify([g]),
      sample_values: JSON.stringify([g.text]),
    });
  });

  if (rows.length) {
    await db.insertInto("template_variables").values(rows).execute();
  }

  revalidatePath("/sablony");
  redirect(`/sablony/${template.id}`);
}

export async function deleteTemplate(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  if (!id) return;
  await db.deleteFrom("templates").where("id", "=", id).execute();
  revalidatePath("/sablony");
}
