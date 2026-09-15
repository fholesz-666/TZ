/**
 * Přístup k databázi.
 *
 * Schéma je v `db/schema.sql` – jeden zdroj pravdy, čitelný i bez nástrojů.
 * Typy níže ho popisují pro TypeScript; když se schéma změní, změní se
 * i tady, a překladač ukáže, co všechno je potřeba dotáhnout.
 */
import { Generated, Kysely, PostgresDialect, sql } from "kysely";
import { Pool } from "pg";

export type Json = Record<string, unknown>;

export interface UsersTable {
  id: Generated<string>;
  email: string;
  name: string | null;
  created_at: Generated<Date>;
}

export interface CompaniesTable {
  id: Generated<string>;
  owner_id: string;
  name: string;
  ico: string | null;
  address: string | null;
  logo_key: string | null;
  settings: Generated<Json>;
  constants: Generated<Json>;
  created_at: Generated<Date>;
}

export interface TemplateSetsTable {
  id: Generated<string>;
  company_id: string;
  code: string;
  name: string;
  documents: Generated<unknown>;
  created_at: Generated<Date>;
}

export interface TemplatesTable {
  id: Generated<string>;
  set_id: string;
  doc_code: string;
  title: string;
  file_key: string;
  file_hash: string;
  manifest: Json;
  /** k_potvrzeni = průvodce importem ještě neproběhl */
  status: Generated<string>;
  created_at: Generated<Date>;
  updated_at: Generated<Date>;
}

export interface TemplateVariablesTable {
  id: Generated<string>;
  template_id: string;
  key: string;
  label: string | null;
  /** variable | generated | fixed */
  role: string;
  bind_path: string | null;
  data_type: Generated<string>;
  unit: string | null;
  enum_values: unknown;
  is_company_constant: Generated<boolean>;
  required: Generated<boolean>;
  confirmed: Generated<boolean>;
  evidence: Generated<Json>;
  confidence: Generated<number>;
  occurrences: Generated<unknown>;
  sample_values: Generated<unknown>;
}

export interface ProjectsTable {
  id: Generated<string>;
  owner_id: string;
  company_id: string;
  set_id: string;
  order_number: string;
  name: string;
  status: Generated<string>;
  data: Generated<Json>;
  provenance: Generated<Json>;
  current_version: string | null;
  created_at: Generated<Date>;
  updated_at: Generated<Date>;
  archived_at: Date | null;
}

export interface Database {
  users: UsersTable;
  companies: CompaniesTable;
  template_sets: TemplateSetsTable;
  templates: TemplatesTable;
  template_variables: TemplateVariablesTable;
  projects: ProjectsTable;
}

declare global {
  // eslint-disable-next-line no-var
  var __fvePool: Pool | undefined;
}

const pool =
  globalThis.__fvePool ??
  new Pool({
    connectionString: process.env.DATABASE_URL,
    max: 5,
  });
if (process.env.NODE_ENV !== "production") globalThis.__fvePool = pool;

export const db = new Kysely<Database>({
  dialect: new PostgresDialect({ pool }),
});

export { sql };

/**
 * Dokud není přihlašování, pracuje se v jednom výchozím prostoru.
 * Vytvoří se při prvním použití, aby aplikace fungovala hned po nasazení.
 */
export async function ensureWorkspace() {
  const email = process.env.DEFAULT_USER_EMAIL ?? "projekce@fvsol.cz";
  let user = await db
    .selectFrom("users")
    .selectAll()
    .where("email", "=", email)
    .executeTakeFirst();
  if (!user) {
    user = await db
      .insertInto("users")
      .values({ email, name: "Projektant" })
      .returningAll()
      .executeTakeFirstOrThrow();
  }
  return user;
}

export async function listSets() {
  return db
    .selectFrom("template_sets")
    .innerJoin("companies", "companies.id", "template_sets.company_id")
    .select([
      "template_sets.id as id",
      "template_sets.code as code",
      "template_sets.name as name",
      "companies.name as company",
    ])
    .orderBy("template_sets.code")
    .execute();
}
