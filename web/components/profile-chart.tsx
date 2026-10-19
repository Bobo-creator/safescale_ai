"use client";

import { SIGNAL_STYLES, SIGNAL_WORDS, lift, percent } from "@/lib/format";
import type { CategoryStat } from "@/lib/types";

/**
 * The hazard profile: each bar is the share of similar recalls with that hazard; the tick marks
 * its share among all recalls, so the gap between them is the lift.
 */
export function ProfileChart({
  profile,
  relevant,
  selected,
  onSelect,
}: {
  profile: CategoryStat[];
  relevant: number;
  selected: string | null;
  onSelect: (code: string | null) => void;
}) {
  if (!profile.length) return null;
  return (
    <section aria-labelledby="profile-heading" className="mt-10">
      <h3 id="profile-heading" className="text-lg font-semibold">
        Hazards in similar recalls
      </h3>
      <p className="mt-1 text-sm text-graphite">
        Each bar is the share of the {relevant} similar recalls with that hazard. The tick marks its
        usual rate across all 10,039 recalls. Select a hazard to list its recalls.
      </p>
      <ul className="mt-5 space-y-1">
        {profile.map((s) => {
          const style = SIGNAL_STYLES[s.signal];
          const isSelected = selected === s.code;
          return (
            <li key={s.code}>
              <button
                type="button"
                aria-pressed={isSelected}
                aria-label={`${s.label}: ${s.count} of ${relevant} similar recalls (${percent(s.share)}), ${lift(s.lift)} its share of all recalls (${percent(s.base_rate)}). ${SIGNAL_WORDS[s.signal]} signal.`}
                onClick={() => onSelect(isSelected ? null : s.code)}
                className={`grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-5 gap-y-2 rounded-md px-2 py-2.5 text-left sm:grid-cols-[12rem_minmax(0,1fr)_10.5rem] ${
                  isSelected ? "bg-cobalt-soft" : "hover:bg-sheet"
                }`}
              >
                <span className="font-medium leading-snug">{s.label}</span>
                <span className="relative order-last col-span-2 block h-4 rounded-sm bg-rule/60 sm:order-none sm:col-span-1" aria-hidden>
                  <span
                    className={`absolute inset-y-0 left-0 rounded-sm ${style.bar}`}
                    style={{ width: `${Math.max(2, s.share * 100)}%` }}
                  />
                  <span
                    className="absolute -inset-y-1.5 w-0.5 bg-ink"
                    style={{ left: `${s.base_rate * 100}%` }}
                    title={`${percent(s.base_rate)} of all recalls`}
                  />
                </span>
                <span className="text-right text-sm leading-tight">
                  <span className="block">
                    <span className="font-semibold">
                      {s.count} of {relevant} ({percent(s.share)})
                    </span>{" "}
                    <span className={`font-semibold ${style.text}`}>{SIGNAL_WORDS[s.signal]}</span>
                  </span>
                  <span className="block text-graphite">{lift(s.lift)} its usual rate</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
