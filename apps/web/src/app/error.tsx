"use client";

/**
 * Chybová stránka. Místo stopy z Node ukazuje, co je nejspíš špatně —
 * skoro vždycky jde o nespuštěnou databázi nebo dokumentovou službu.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const msg = error.message ?? "";
  const dbDown =
    /ECONNREFUSED|ENOTFOUND|password authentication|database .* does not exist|connect/i.test(
      msg,
    );
  const engineDown = /8100|Dokumentová služba|fetch failed/i.test(msg);

  return (
    <div className="surface p-6">
      <h1 className="text-lg font-semibold">Něco se nepovedlo</h1>

      <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
        {dbDown
          ? "Aplikace se nedostala k databázi."
          : engineDown
            ? "Aplikace se nedostala k dokumentové službě."
            : "Aplikace narazila na chybu."}
      </p>

      <ol
        className="mt-4 list-decimal space-y-1.5 pl-5 text-sm"
        style={{ color: "var(--muted)" }}
      >
        {dbDown && (
          <>
            <li>
              Běží PostgreSQL? Databáze se vytvoří příkazem{" "}
              <span className="literal">psql -d fve -f db/schema.sql</span>.
            </li>
            <li>
              Je v souboru <span className="literal">apps/web/.env</span> správné{" "}
              <span className="literal">DATABASE_URL</span>?
            </li>
          </>
        )}
        {engineDown && (
          <li>
            Spusťte v <span className="literal">packages/docx-engine</span>{" "}
            příkaz <span className="literal">uvicorn app.main:app --port 8100</span>.
          </li>
        )}
        {!dbDown && !engineDown && (
          <li>Podrobnosti jsou v konzoli, kde běží vývojový server.</li>
        )}
      </ol>

      <pre
        className="mt-4 overflow-x-auto rounded-lg p-3 text-xs"
        style={{ background: "#f4f5f7", color: "var(--muted)" }}
      >
        {msg || "bez popisu"}
      </pre>

      <button className="btn mt-4" onClick={reset}>
        Zkusit znovu
      </button>
    </div>
  );
}
