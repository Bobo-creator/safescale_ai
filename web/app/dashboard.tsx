"use client";

import { useState } from "react";
import { ApiError, analyze } from "@/lib/api";
import { EXAMPLES } from "@/lib/examples";
import type { HazardReport } from "@/lib/types";

export function Dashboard() {
  const [query, setQuery] = useState<string>(EXAMPLES[0].text);
  const [report, setReport] = useState<HazardReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setReport(await analyze({ query, k: 25, method: "vector" }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-3xl p-6">
      <h1 className="text-2xl font-semibold">SafeScale AI</h1>
      <textarea
        className="mt-4 w-full rounded border p-2"
        rows={3}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <button className="mt-2 rounded bg-black px-4 py-2 text-white" disabled={busy} onClick={run}>
        {busy ? "Analyzing…" : "Analyze"}
      </button>
      {error && <p role="alert">{error}</p>}
      {report && (
        <section className="mt-6">
          <p data-testid="signal">Signal: {report.overall_signal}</p>
          <ol className="mt-2 list-decimal pl-6">
            {report.matches.slice(0, 5).map((m) => (
              <li key={m.recall_id}>{m.title}</li>
            ))}
          </ol>
        </section>
      )}
    </main>
  );
}
