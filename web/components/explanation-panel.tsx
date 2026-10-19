"use client";

import { categoryLabel } from "@/lib/format";
import type { Explanation, HazardReport } from "@/lib/types";
import { Citations } from "./citations";
import { useEvidence } from "./evidence-context";

export type ExplanationState =
  | { status: "loading" }
  | { status: "ready"; explanation: Explanation }
  | { status: "skipped"; message: string }
  | { status: "error"; message: string };

export function ExplanationPanel({ state, report }: { state: ExplanationState; report: HazardReport }) {
  const { rankOf, focus } = useEvidence();
  const areaTitles = Object.fromEntries(report.investigation_areas.map((a) => [a.id, a.title]));

  return (
    <section aria-labelledby="explanation-heading" aria-busy={state.status === "loading"} className="mt-12">
      <h3 id="explanation-heading" className="text-lg font-semibold">
        What the similar recalls show
      </h3>

      {state.status === "loading" && (
        <div className="mt-4 max-w-2xl" role="status">
          <p className="text-graphite">Writing a cited explanation. This takes about 10 seconds.</p>
          <div className="mt-4 space-y-3" aria-hidden>
            {[92, 100, 78, 85].map((w) => (
              <div key={w} className="h-3 animate-pulse rounded bg-rule/70" style={{ width: `${w}%` }} />
            ))}
          </div>
        </div>
      )}

      {(state.status === "skipped" || state.status === "error") && (
        <p className="mt-3 max-w-2xl text-graphite" role={state.status === "error" ? "alert" : undefined}>
          {state.message}
        </p>
      )}

      {state.status === "ready" && (
        <div className="mt-4 max-w-2xl font-serif text-[1.07rem] leading-[1.75]">
          {state.explanation.notice && <p className="text-graphite">{state.explanation.notice}</p>}

          {state.explanation.summary.length > 0 && (
            <p>
              {state.explanation.summary.map((s, i) => (
                <span key={i}>
                  {s.text} <Citations ids={s.citations} />{" "}
                </span>
              ))}
            </p>
          )}

          {state.explanation.hazards.map((h) => (
            <div key={h.category} className="mt-5">
              <h4 className="font-sans text-base font-semibold">{categoryLabel(h.category)}</h4>
              <p className="mt-1">
                {h.sentences.map((s, i) => (
                  <span key={i}>
                    {s.text} <Citations ids={s.citations} />{" "}
                  </span>
                ))}
              </p>
            </div>
          ))}

          {state.explanation.match_reasons.length > 0 && (
            <div className="mt-7">
              <h4 className="font-sans text-base font-semibold">Why these recalls match</h4>
              <ul className="mt-2 space-y-2 font-sans text-[0.95rem] leading-relaxed">
                {state.explanation.match_reasons.map((r) => (
                  <li key={r.recall_id} className="grid grid-cols-[2.5rem_1fr]">
                    <button
                      type="button"
                      onClick={() => focus(r.recall_id)}
                      className="self-start text-left font-semibold text-cobalt"
                      aria-label={`Show similar recall ${rankOf(r.recall_id) ?? r.recall_id}`}
                    >
                      {rankOf(r.recall_id) ?? `#${r.recall_id}`}
                    </button>
                    <span>
                      <span className="text-ink">Shares {r.shared.join(", ")}.</span>
                      {r.different.length > 0 && (
                        <span className="text-graphite"> Differs: {r.different.join(", ")}.</span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {state.explanation.investigation_notes.length > 0 && (
            <div className="mt-7">
              <h4 className="font-sans text-base font-semibold">Why each investigation area</h4>
              <ul className="mt-2 space-y-2">
                {state.explanation.investigation_notes.map((n) => (
                  <li key={n.area_id}>
                    <span className="font-sans font-medium">{areaTitles[n.area_id] ?? n.area_id}.</span>{" "}
                    {n.sentence.text} <Citations ids={n.sentence.citations} />
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p className="mt-7 font-sans text-sm text-graphite">{state.explanation.caveat}</p>
          {state.explanation.validation.fallback_used && (
            <p className="mt-2 font-sans text-sm text-graphite">
              The written explanation didn&apos;t pass our evidence checks, so this summary is
              built directly from the data.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
