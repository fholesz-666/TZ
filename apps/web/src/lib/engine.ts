/**
 * Volání dokumentové služby (Python, OOXML).
 *
 * Volá se výhradně ze serveru. Prohlížeč se k ní nikdy nedostane –
 * jde přes ni obsah cizích souborů a nemá být vystavená ven.
 */
const BASE = process.env.DOCX_ENGINE_URL ?? "http://127.0.0.1:8100";

export interface Occurrence {
  path: string;
  segment: number;
  text: string;
}

export interface ManifestVariable {
  key: string;
  label: string | null;
  mapped: boolean;
  needs_binding?: boolean;
  occurrences: Occurrence[];
  sample_values: string[];
  /** Klíče, které tenhle úsek pokryjí přepisem podle slovníku. */
  covered_by?: string[];
}

export interface Manifest {
  source_file: string;
  sections: number;
  blocks: unknown[];
  variables: ManifestVariable[];
  generated_segments: Occurrence[];
  suspect_labels: Array<Occurrence & { reason: string }>;
  stats: {
    blocks: number;
    variables: number;
    variable_occurrences: number;
    mapped_variables: number;
    generated_segments: number;
    suspect_labels: number;
  };
}

export async function parseTemplate(
  fileName: string,
  bytes: Buffer,
): Promise<Manifest> {
  const form = new FormData();
  form.append("file", new Blob([new Uint8Array(bytes)]), fileName);
  const res = await fetch(`${BASE}/parse`, { method: "POST", body: form });
  if (!res.ok) {
    throw new Error(
      `Dokumentová služba odpověděla ${res.status}: ${await res.text()}`,
    );
  }
  return (await res.json()) as Manifest;
}

export async function engineHealthy(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/health`, {
      signal: AbortSignal.timeout(2000),
    });
    return res.ok;
  } catch {
    return false;
  }
}
