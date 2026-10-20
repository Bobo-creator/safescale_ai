"use client";

import { useCallback, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { EvidenceContext } from "@/components/evidence-context";
import { EvidenceList } from "@/components/evidence-list";
import { type ExplanationState, ExplanationPanel } from "@/components/explanation-panel";
import { InputPanel } from "@/components/input-panel";
import { Investigation } from "@/components/investigation";
import { ProfileChart } from "@/components/profile-chart";
import { SignalSummary } from "@/components/signal-summary";
import { Terms } from "@/components/terms";
import { ApiError, analyze, explain } from "@/lib/api";
import type { HazardReport, Query } from "@/lib/types";

type AnalysisState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; report: HazardReport };

// /analyze?q=… (from the landing page) arrives filled in. Read from the URL in the browser only;
// the server renders the empty form, so the page stays static.
const noSubscribe = () => () => {};
const queryFromUrl = () => new URLSearchParams(window.location.search).get("q") ?? "";
const noQueryOnServer = () => "";

export function Dashboard() {
  const initialQuery = useSyncExternalStore(noSubscribe, queryFromUrl, noQueryOnServer);
  const [analysis, setAnalysis] = useState<AnalysisState>({ status: "idle" });
  const [explanation, setExplanation] = useState<ExplanationState>({ status: "loading" });
  const [selected, setSelected] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const results = useRef<HTMLDivElement>(null);

  async function run(q: Query) {
    controller.current?.abort();
    const ctrl = new AbortController();
    controller.current = ctrl;
    setAnalysis({ status: "loading" });
    setExplanation({ status: "loading" });
    setSelected(null);

    let report: HazardReport;
    try {
      report = await analyze(q, ctrl.signal);
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setAnalysis({ status: "error", message: err instanceof ApiError ? err.message : "Something went wrong." });
      return;
    }
    setAnalysis({ status: "ready", report });
    requestAnimationFrame(() => results.current?.focus({ preventScroll: false }));

    if (report.insufficient_evidence) {
      setExplanation({ status: "skipped", message: "There isn't enough evidence to explain." });
      return;
    }
    try {
      const res = await explain(q, ctrl.signal);
      if (res.explanation) setExplanation({ status: "ready", explanation: res.explanation });
      else setExplanation({ status: "skipped", message: res.notice ?? "No explanation is available." });
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      const message =
        err instanceof ApiError && err.status === 429
          ? `${err.message} The hazard analysis above is complete.`
          : "The written explanation isn't available right now. The hazard analysis above is complete.";
      setExplanation({ status: "error", message });
    }
  }

  const report = analysis.status === "ready" ? analysis.report : null;
  const ranks = useMemo(
    () => new Map(report?.matches.map((m) => [m.recall_id, m.rank]) ?? []),
    [report],
  );
  const focus = useCallback((id: number) => {
    setSelected(null); // a citation may point outside the current filter
    requestAnimationFrame(() => {
      const card = document.getElementById(`recall-${id}`);
      if (!card) return;
      const behavior = matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
      const list = card.closest<HTMLElement>("[data-evidence-scroll]");
      if (list && list.scrollHeight > list.clientHeight) {
        // Desktop: the evidence column scrolls on its own; move it, not the page.
        const offset = card.getBoundingClientRect().top - list.getBoundingClientRect().top;
        list.scrollTo({ top: list.scrollTop + offset - 16, behavior });
      } else {
        card.scrollIntoView({ behavior, block: "start" });
      }
      card.classList.remove("cite-flash");
      void card.offsetWidth; // restart the highlight
      card.classList.add("cite-flash");
      card.focus({ preventScroll: true });
    });
  }, []);
  const links = useMemo(() => ({ rankOf: (id: number) => ranks.get(id) ?? null, focus }), [ranks, focus]);
  const selectedStat = report?.profile.find((s) => s.code === selected) ?? null;

  return (
    <EvidenceContext value={links}>
      <InputPanel
        key={initialQuery}
        busy={analysis.status === "loading"}
        onSubmit={run}
        initialQuery={initialQuery}
      />

      <div ref={results} tabIndex={-1} className="outline-none">
        {analysis.status === "loading" && <ResultsSkeleton />}
        {analysis.status === "error" && (
          <p className="mx-auto max-w-7xl px-5 font-medium text-high sm:px-8" role="alert">
            {analysis.message}
          </p>
        )}
        {report && (
          <div className="border-t border-rule bg-sheet">
            <div className="mx-auto grid max-w-7xl gap-x-12 gap-y-12 px-5 py-10 sm:px-8 lg:grid-cols-[minmax(0,1fr)_26rem]">
              <div>
                <SignalSummary report={report} />
                <ProfileChart
                  profile={report.profile}
                  relevant={report.relevant}
                  selected={selected}
                  onSelect={setSelected}
                />
                <Terms shared={report.shared_terms} failure={report.failure_terms} />
                <ExplanationPanel state={explanation} report={report} />
                <Investigation
                  areas={report.investigation_areas}
                  standards={report.standards}
                  relevant={report.relevant}
                />
              </div>
              <aside data-evidence-scroll className="lg:sticky lg:top-6 lg:max-h-[calc(100dvh-8rem)] lg:self-start lg:overflow-y-auto lg:pr-2">
                <EvidenceList
                  matches={report.matches}
                  filter={selectedStat?.recall_ids ?? null}
                  filterLabel={selectedStat?.label ?? null}
                  onClearFilter={() => setSelected(null)}
                />
              </aside>
            </div>
          </div>
        )}
      </div>
    </EvidenceContext>
  );
}


/** Stands in for the results while the closest recalls are found (about a second). */
function ResultsSkeleton() {
  const bar = "animate-pulse rounded bg-rule/70";
  return (
    <div className="border-t border-rule bg-sheet" role="status">
      <span className="sr-only">Finding similar recalls…</span>
      <div className="mx-auto grid max-w-7xl gap-x-12 gap-y-10 px-5 py-10 sm:px-8 lg:grid-cols-[minmax(0,1fr)_26rem]" aria-hidden>
        <div>
          <div className={`h-6 w-40 ${bar}`} />
          <div className={`mt-4 h-8 w-4/5 ${bar}`} />
          <div className={`mt-3 h-4 w-3/5 ${bar}`} />
          <div className="mt-10 space-y-5">
            {[56, 56, 28, 28].map((w, i) => (
              <div key={i} className="grid grid-cols-[12rem_1fr] items-center gap-5">
                <div className={`h-4 w-32 ${bar}`} />
                <div className="h-4 rounded-sm bg-rule/40">
                  <div className={`h-4 ${bar}`} style={{ width: `${w}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="space-y-6">
          {[0, 1, 2].map((i) => (
            <div key={i} className="space-y-2">
              <div className={`h-4 w-11/12 ${bar}`} />
              <div className={`h-3 w-1/2 ${bar}`} />
              <div className={`h-12 w-full ${bar}`} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
