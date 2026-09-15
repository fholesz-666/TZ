/**
 * Cesty v datovém modelu projektu, na které se dá proměnná navázat.
 *
 * Seznam se čte z `docs/project-data.schema.json`, aby existoval jeden
 * zdroj pravdy. Kdyby se psal ručně, rozešel by se s modelem během týdne.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

export interface ModelPath {
  path: string;
  title: string;
  group: string;
  derived: boolean;
}

interface SchemaNode {
  type?: string | string[];
  title?: string;
  description?: string;
  properties?: Record<string, SchemaNode>;
  items?: SchemaNode;
  "x-derived"?: string;
}

const SCHEMA_FILE = resolve(
  process.env.PROJECT_SCHEMA ?? "../../docs/project-data.schema.json",
);

function flatten(
  node: SchemaNode,
  prefix: string,
  group: string,
  out: ModelPath[],
): void {
  if (!node.properties) return;
  for (const [name, child] of Object.entries(node.properties)) {
    const path = prefix ? `${prefix}.${name}` : name;
    const isObject =
      child.properties !== undefined ||
      child.type === "object" ||
      (Array.isArray(child.type) && child.type.includes("object"));
    if (isObject && child.properties) {
      flatten(child, path, prefix ? group : name, out);
      continue;
    }
    if (child.type === "array") {
      // Pole se jako celek navázat nedá – řeší ho opakující se bloky.
      // Tabulky v šabloně ale popisují první položku („Parametry
      // použitého střídače INV1“), takže ta je adresovatelná.
      if (child.items?.properties) {
        flatten(child.items, `${path}.0`, prefix ? group : name, out);
      }
      continue;
    }
    out.push({
      path,
      title: child.description ?? child.title ?? name,
      group: prefix ? group : name,
      derived: Boolean(child["x-derived"]),
    });
  }
}

let cache: ModelPath[] | null = null;

export function modelPaths(): ModelPath[] {
  if (cache) return cache;
  const schema = JSON.parse(readFileSync(SCHEMA_FILE, "utf8")) as SchemaNode;
  const out: ModelPath[] = [];
  flatten(schema, "", "", out);
  out.sort((a, b) => a.path.localeCompare(b.path, "cs"));
  cache = out;
  return out;
}

export function isKnownPath(path: string): boolean {
  return modelPaths().some((p) => p.path === path);
}
