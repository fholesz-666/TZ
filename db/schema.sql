-- Schéma databáze aplikace pro tvorbu FVE dokumentace.
--
-- Projektová data jsou JSONB, protože struktura se liší podle firmy
-- a bude se vyvíjet; validuje je JSON Schema, ne databáze.
-- Katalogy, verze, šablony a dokumenty jsou relační – tam potřebujeme
-- integritu a dotazy.
--
-- Verze projektu je neměnný snímek. Původní se nikdy nepřepisuje (bod 49).

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ------------------------------------------------------------ uživatelé

CREATE TABLE IF NOT EXISTS users (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email       text UNIQUE NOT NULL,
  name        text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- --------------------------------------------------- firmy a zpracovatelé

-- Zpracovatel dokumentace. Na něj jsou navázané firemní konstanty –
-- autorizovaná osoba, zhotovitel, razítko, logo.
CREATE TABLE IF NOT EXISTS companies (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name        text NOT NULL,
  ico         text,
  address     text,
  logo_key    text,
  settings    jsonb NOT NULL DEFAULT '{}'::jsonb,   -- označení rozvaděčů, číselné řady
  constants   jsonb NOT NULL DEFAULT '{}'::jsonb,   -- co se u firmy nikdy nemění
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (owner_id, name)
);

-- Dokumentační systém: V1 JABLONEC, V2 UNIVERZÁL, V3 SIMPLY.
-- Není to verze téhož dokumentu, ale jiný způsob práce.
CREATE TABLE IF NOT EXISTS template_sets (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id  uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  code        text NOT NULL,
  name        text NOT NULL,
  documents   jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (company_id, code)
);

-- Jedna šablona = jeden typ dokumentu. Originální .docx zůstává
-- nedotčený v úložišti; manifest drží anotace z parseru.
CREATE TABLE IF NOT EXISTS templates (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  set_id      uuid NOT NULL REFERENCES template_sets(id) ON DELETE CASCADE,
  doc_code    text NOT NULL,          -- A | B | D.1.1.2 | D.2.2 | VYKAZ
  title       text NOT NULL,
  file_key    text NOT NULL,
  file_hash   text NOT NULL,
  manifest    jsonb NOT NULL,
  status      text NOT NULL DEFAULT 'k_potvrzeni',  -- k_potvrzeni | potvrzena
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (set_id, doc_code)
);

-- Kandidát na proměnnou z importu, potvrzený uživatelem.
-- `evidence` nese výsledek křížové analýzy referenčních projektů
-- („mění se ve 4 z 5 projektů“) – body 62 a 67.
CREATE TABLE IF NOT EXISTS template_variables (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  template_id         uuid NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
  key                 text NOT NULL,
  label               text,
  role                text NOT NULL,          -- variable | generated | fixed
  bind_path           text,
  data_type           text NOT NULL DEFAULT 'text',
  unit                text,
  enum_values         jsonb,
  is_company_constant boolean NOT NULL DEFAULT false,
  required            boolean NOT NULL DEFAULT false,
  confirmed           boolean NOT NULL DEFAULT false,
  evidence            jsonb NOT NULL DEFAULT '{}'::jsonb,
  confidence          real NOT NULL DEFAULT 0,
  occurrences         jsonb NOT NULL DEFAULT '[]'::jsonb,
  sample_values       jsonb NOT NULL DEFAULT '[]'::jsonb,
  UNIQUE (template_id, key)
);

-- Pravidlo, kterým uživatel opravil závěr analýzy (bod 68).
CREATE TABLE IF NOT EXISTS learned_rules (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scope       text NOT NULL DEFAULT 'global',
  matcher     jsonb NOT NULL,
  decision    jsonb NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------- projekty

CREATE TABLE IF NOT EXISTS projects (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id        uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  company_id      uuid NOT NULL REFERENCES companies(id),
  set_id          uuid NOT NULL REFERENCES template_sets(id),
  order_number    text NOT NULL,
  name            text NOT NULL,
  status          text NOT NULL DEFAULT 'rozpracovany',
  data            jsonb NOT NULL DEFAULT '{}'::jsonb,
  provenance      jsonb NOT NULL DEFAULT '{}'::jsonb,
  current_version text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  archived_at     timestamptz,
  UNIQUE (owner_id, order_number)
);
CREATE INDEX IF NOT EXISTS projects_owner_status ON projects (owner_id, status);

-- Neměnný snímek projektu.
CREATE TABLE IF NOT EXISTS project_versions (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  label       text NOT NULL,
  parent_id   uuid REFERENCES project_versions(id),
  data        jsonb NOT NULL,
  provenance  jsonb NOT NULL DEFAULT '{}'::jsonb,
  changelog   jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_by  text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, label)
);

CREATE TABLE IF NOT EXISTS project_files (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind        text NOT NULL,
  file_name   text NOT NULL,
  file_key    text NOT NULL,
  mime_type   text NOT NULL,
  size_bytes  bigint NOT NULL,
  hash        text NOT NULL,
  extraction  jsonb,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- Vygenerovaný soubor je vždy vázaný na projekt a verzi (bod 38).
CREATE TABLE IF NOT EXISTS generated_documents (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id      uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  version_id      uuid NOT NULL REFERENCES project_versions(id),
  doc_code        text NOT NULL,
  revision        text NOT NULL DEFAULT 'Rev00',
  file_key        text NOT NULL,
  file_name       text NOT NULL,
  inputs_hash     text NOT NULL,
  manually_edited boolean NOT NULL DEFAULT false,
  unresolved      jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS generated_documents_project ON generated_documents (project_id, doc_code);

-- ---------------------------------------------------------- výkaz výměr

CREATE TABLE IF NOT EXISTS boq_templates (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id  uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  name        text NOT NULL,
  structure   jsonb NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS boq_items (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id   uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  section      integer NOT NULL,
  section_name text NOT NULL,
  position     integer NOT NULL,
  name         text NOT NULL,
  description  text,
  supplier     text,
  unit         text NOT NULL,
  -- text, ne číslo: „dle trasy“ a „netýká se“ jsou platné hodnoty
  quantity     text NOT NULL,
  formula      text,
  source       text NOT NULL DEFAULT 'user',
  needs_review boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS boq_items_project ON boq_items (project_id, section, position);

-- ------------------------------------------------------ katalog zařízení

CREATE TABLE IF NOT EXISTS devices (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  category      text NOT NULL,   -- panel | inverter | optimizer | battery | switchboard | cable
  manufacturer  text NOT NULL,
  model         text NOT NULL,
  params        jsonb NOT NULL DEFAULT '{}'::jsonb,
  source_url    text,
  datasheet_key text,
  verified_by   text,
  verified_at   timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (category, manufacturer, model)
);
CREATE INDEX IF NOT EXISTS devices_category ON devices (category);

-- ------------------------------------------------------------- validace

-- Pravidla pre-flight kontroly jsou data, ne kód – dají se přidávat
-- bez nasazení nové verze.
CREATE TABLE IF NOT EXISTS validation_rules (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code       text UNIQUE NOT NULL,
  title      text NOT NULL,
  severity   text NOT NULL,
  expression text NOT NULL,
  message    text NOT NULL,
  scope      text NOT NULL DEFAULT 'global',
  enabled    boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS audit_log (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid REFERENCES users(id),
  entity     text NOT NULL,
  entity_id  text NOT NULL,
  action     text NOT NULL,
  before     jsonb,
  after      jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_log_entity ON audit_log (entity, entity_id);
