"use client";

import type { Area, StandardStat } from "@/lib/types";
import { Citations } from "./citations";

export function Investigation({
  areas,
  standards,
  relevant,
}: {
  areas: Area[];
  standards: StandardStat[];
  relevant: number;
}) {
  if (!areas.length && !standards.length) return null;
  return (
    <section aria-labelledby="investigate-heading" className="mt-12">
      <h3 id="investigate-heading" className="text-lg font-semibold">
        Areas to consider investigating
      </h3>
      <p className="mt-1 text-sm text-graphite">
        Recommendations for review, based on what failed in similar recalls. Not compliance
        determinations.
      </p>
      <ul className="mt-5 divide-y divide-rule border-y border-rule">
        {areas.map((a) => (
          <li key={a.id} className="py-4">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4">
              <h4 className="font-semibold">{a.title}</h4>
              <span className="text-sm text-graphite">
                {a.support} of {relevant} similar recalls <Citations ids={a.recall_ids.slice(0, 6)} />
              </span>
            </div>
            <ul className="mt-2 space-y-1 text-[0.95rem]">
              {a.checks.map((c) => (
                <li key={c} className="flex gap-2">
                  <span aria-hidden className="mt-2 inline-block size-1.5 shrink-0 rounded-full bg-graphite/60" />
                  {c}
                </li>
              ))}
            </ul>
            {a.terms.length > 0 && (
              <p className="mt-2 text-sm text-graphite">Seen in those recalls: {a.terms.join(", ")}</p>
            )}
          </li>
        ))}
      </ul>

      {standards.length > 0 && (
        <div className="mt-8">
          <h4 className="font-semibold">Standards that similar recalls failed</h4>
          <p className="mt-1 text-sm text-graphite">Review whether they apply to your product.</p>
          <ul className="mt-3 space-y-1.5">
            {standards.map((s) => (
              <li key={s.standard} className="flex flex-wrap items-baseline justify-between gap-x-4">
                <span>{s.standard}</span>
                <span className="text-sm text-graphite">
                  {s.count} similar recalls <Citations ids={s.recall_ids.slice(0, 6)} />
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
