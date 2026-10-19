"use client";

import { useCallback, useMemo, useRef, useState } from "react";
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

export function Dashboard() {
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
      <InputPanel busy={analysis.status === "loading"} onSubmit={run} />

      <div ref={results} tabIndex={-1} className="outline-none">
        {analysis.status === "loading" && (
          <p className="mx-auto max-w-7xl px-5 text-graphite sm:px-8" role="status">
            Finding similar recalls…
          </p>
        )}
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
