"use server";

import { revalidatePath } from "next/cache";

import { db } from "@/lib/db";
import { isKnownPath } from "@/lib/model-paths";

/**
 * Uložení rozhodnutí z průvodce importem.
 *
 * Uživatel má poslední slovo (body 43 a 68): co označí jako fixní text
 * nebo firemní konstantu, se příště nenabízí jako proměnná projektu.
 */
export async function saveDecisions(formData: FormData) {
  const templateId = String(formData.get("templateId") ?? "");
  if (!templateId) throw new Error("Chybí šablona.");

  const rows = await db
    .selectFrom("template_variables")
    .select(["id", "key"])
    .where("template_id", "=", templateId)
    .execute();

  for (const row of rows) {
    const role = String(formData.get(`role.${row.id}`) ?? "variable");
    const bindRaw = String(formData.get(`bind.${row.id}`) ?? "").trim();
    const isConstant = formData.get(`const.${row.id}`) === "on";

    // Navázat se dá jen na cestu, která v modelu opravdu existuje –
    // jinak by dokument tiše zůstal nevyplněný.
    const bind =
      role === "variable" && bindRaw && isKnownPath(bindRaw) ? bindRaw : null;

    await db
      .updateTable("template_variables")
      .set({
        role,
        bind_path: bind,
        is_company_constant: role === "variable" ? isConstant : false,
        confirmed: true,
      })
      .where("id", "=", row.id)
      .execute();
  }

  await db
    .updateTable("templates")
    .set({ status: "potvrzena", updated_at: new Date() })
    .where("id", "=", templateId)
    .execute();

  revalidatePath(`/sablony/${templateId}`);
  revalidatePath("/sablony");
}

/** Vrátí šablonu do rozpracovaného stavu, aby šla znovu projít. */
export async function reopenTemplate(formData: FormData) {
  const templateId = String(formData.get("templateId") ?? "");
  if (!templateId) return;
  await db
    .updateTable("templates")
    .set({ status: "k_potvrzeni" })
    .where("id", "=", templateId)
    .execute();
  revalidatePath(`/sablony/${templateId}`);
}
