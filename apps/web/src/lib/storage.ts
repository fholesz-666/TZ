/**
 * Úložiště souborů.
 *
 * Šablony, podklady a vygenerované dokumenty nepatří do databáze.
 * Lokálně se ukládají na disk, v provozu do S3/R2 – rozhraní je stejné,
 * takže se mění jen ovladač, ne aplikace.
 */
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";

const ROOT = resolve(process.env.STORAGE_DIR ?? "../../data/storage");

export function hashOf(buffer: Buffer): string {
  return createHash("sha256").update(buffer).digest("hex").slice(0, 16);
}

/** Klíč je cesta v úložišti, ne jméno souboru na disku uživatele. */
export function keyFor(parts: string[]): string {
  return parts
    .map((p) => p.replace(/[^\p{L}\p{N}._-]+/gu, "_"))
    .join("/");
}

export async function put(key: string, data: Buffer): Promise<string> {
  const target = join(ROOT, key);
  await mkdir(dirname(target), { recursive: true });
  await writeFile(target, data);
  return key;
}

export async function get(key: string): Promise<Buffer> {
  return readFile(join(ROOT, key));
}
