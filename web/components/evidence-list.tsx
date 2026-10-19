"use client";

import { categoryLabel, formatDate } from "@/lib/format";
import type { Match } from "@/lib/types";

function EvidenceCard({ m }: { m: Match }) {
  const quote = m.hazard_text ?? m.labels[0]?.evidence;
  return (
    <li id={`recall-${m.recall_id}`} className="scroll-mt-24 rounded-md px-3 py-4" tabIndex={-1}>
      <div className="grid grid-cols-[2rem_1fr] gap-x-2">
        <span className="pt-0.5 text-lg font-semibold text-graphite">{m.rank}</span>
        <div className="min-w-0">
          <h4 className="font-medium leading-snug">{m.title}</h4>
          <p className="mt-1 flex flex-wrap items-center gap-x-3 text-sm text-graphite">
            <span>{formatDate(m.recall_date)}</span>
            <span className="flex items-center gap-1.5" title="Similarity to your description">
              <span className="relative inline-block h-1.5 w-14 rounded-full bg-rule" aria-hidden>
                <span
                  className="absolute inset-y-0 left-0 rounded-full bg-cobalt"
                  style={{ width: `${Math.min(100, (m.cosine / 0.7) * 100)}%` }}
                />
              </span>
              similarity {m.cosine.toFixed(2)}
            </span>
          </p>
          {!m.relevant && (
            <p className="mt-1 text-sm font-medium text-moderate">Weak match, not counted in the profile</p>
          )}
          {m.labels.length > 0 && (
            <p className="mt-2 flex flex-wrap gap-1.5">
              {m.labels.map((l) => (
                <span key={l.category} className="rounded bg-paper px-1.5 py-0.5 text-xs text-ink ring-1 ring-rule">
                  {categoryLabel(l.category)}
                </span>
              ))}
            </p>
          )}
          {quote && <blockquote className="mt-2 line-clamp-4 border-l-2 border-rule pl-3 text-sm text-graphite">{quote}</blockquote>}
          <a
            href={m.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-block text-sm text-cobalt underline decoration-cobalt/30 underline-offset-4 hover:decoration-cobalt"
          >
            Read the CPSC recall notice<span className="sr-only"> (opens in a new tab)</span>
          </a>
        </div>
      </div>
    </li>
  );
}

export function EvidenceList({
  matches,
  filter,
  filterLabel,
  onClearFilter,
}: {
  matches: Match[];
  filter: number[] | null;
  filterLabel: string | null;
  onClearFilter: () => void;
}) {
  const shown = filter ? matches.filter((m) => filter.includes(m.recall_id)) : matches;
  return (
    <section aria-labelledby="evidence-heading">
      <div className="flex items-baseline justify-between gap-4">
        <h3 id="evidence-heading" className="text-lg font-semibold">
          Similar recalls
        </h3>
        <span className="text-sm text-graphite">
          {filter ? `${shown.length} with ${filterLabel?.toLowerCase()}` : `${matches.length} closest`}
        </span>
      </div>
      {filter && (
        <button type="button" onClick={onClearFilter} className="mt-1 text-sm text-cobalt underline underline-offset-4">
          Show all {matches.length}
        </button>
      )}
      <ol className="mt-2 divide-y divide-rule">
        {shown.map((m) => (
          <EvidenceCard key={m.recall_id} m={m} />
        ))}
      </ol>
    </section>
  );
}
