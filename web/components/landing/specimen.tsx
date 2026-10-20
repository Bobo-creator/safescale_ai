import { SIGNAL_STYLES, SIGNAL_WORDS, lift, percent } from "@/lib/format";
import type { Signal } from "@/lib/types";

// A real result from production (2026-10-20) for the brief's example description.
export const NIGHT_LIGHT =
  "Rechargeable children's night light using a 2000 mAh lithium-ion battery, USB-C charging, ABS plastic housing, and LED lighting.";

// Base rates are each hazard's share of all 10,039 recalls; the multiple is computed from them so it
// rounds exactly as the app does.
const ROWS: { label: string; count: number; share: number; base: number; signal: Signal }[] = [
  { label: "Fire / overheating", count: 14, share: 0.56, base: 3009 / 10039, signal: "HIGH" },
  { label: "Burn", count: 14, share: 0.56, base: 1751 / 10039, signal: "HIGH" },
  { label: "Electrical shock", count: 7, share: 0.28, base: 662 / 10039, signal: "MODERATE" },
  { label: "Poisoning / toxic exposure", count: 7, share: 0.28, base: 1145 / 10039, signal: "MODERATE" },
];

export function StripRow({
  row,
  index = 0,
  animate = false,
  stacked = false,
}: {
  row: (typeof ROWS)[number];
  index?: number;
  animate?: boolean;
  /** Bar on its own line below the label, for narrow containers. */
  stacked?: boolean;
}) {
  const style = SIGNAL_STYLES[row.signal];
  const delay = { animationDelay: `${200 + index * 120}ms` };
  return (
    <div
      className={`grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1.5 ${
        stacked ? "" : "sm:grid-cols-[10rem_minmax(0,1fr)_9.75rem]"
      }`}
    >
      <span className="text-sm font-medium">{row.label}</span>
      <span
        className={`relative order-last col-span-2 block h-3.5 rounded-sm bg-rule/60 ${
          stacked ? "" : "sm:order-none sm:col-span-1"
        }`}
      >
        <span
          className={`absolute inset-y-0 left-0 rounded-sm ${style.bar} ${animate ? "strip-grow" : ""}`}
          style={{ width: `${row.share * 100}%`, ...(animate ? delay : {}) }}
        />
        <span
          className={`absolute -inset-y-1.5 w-0.5 bg-ink ${animate ? "tick-in" : ""}`}
          style={{ left: `${row.base * 100}%`, ...(animate ? { animationDelay: `${1000 + index * 120}ms` } : {}) }}
        />
      </span>
      <span className="text-right text-xs leading-tight">
        <span className="block">
          <span className="font-semibold">
            {row.count} of 25 ({percent(row.share)})
          </span>{" "}
          <span className={`font-semibold ${style.text}`}>{SIGNAL_WORDS[row.signal]}</span>
        </span>
        <span className="block text-graphite">{lift(row.share / row.base)} its usual rate</span>
      </span>
    </div>
  );
}

export const SPECIMEN_ROWS = ROWS;

/** The hero: the brief's example description and its real hazard profile. */
export function Specimen() {
  const high = SIGNAL_STYLES.HIGH;
  return (
    <figure className="rounded-lg border border-rule bg-sheet shadow-[0_1px_0_rgba(27,37,51,0.04),0_12px_32px_-16px_rgba(27,37,51,0.25)]">
      <div className="border-b border-rule px-5 py-4">
        <p className="text-xs text-graphite">Product description</p>
        <p className="mt-1 leading-snug">{NIGHT_LIGHT}</p>
      </div>
      <div className="px-5 py-5">
        <p className={`inline-flex items-center gap-2 rounded px-2 py-0.5 text-xs font-semibold ${high.bg} ${high.text}`}>
          <span className={`inline-block size-1.5 rounded-full ${high.bar}`} aria-hidden />
          High historical signal
        </p>
        <p className="mt-2 font-semibold leading-snug">
          Fire / overheating and burn recur in similar recalls
        </p>
        <div className="mt-5 space-y-4" aria-hidden>
          {ROWS.map((row, i) => (
            <StripRow key={row.label} row={row} index={i} animate />
          ))}
        </div>
        <p className="sr-only">
          Of the 25 most similar recalls, 14 involved fire or overheating, 1.9 times its usual rate,
          and 14 involved burns, 3.2 times its usual rate.
        </p>
        <div className="mt-6 grid grid-cols-[1.5rem_1fr] gap-x-2 border-t border-rule pt-4">
          <span className="font-semibold text-graphite">1</span>
          <div>
            <p className="text-sm font-medium leading-snug">
              Rechargeable Portable Lamps with Lithium-Ion Batteries Recalled Due to Fire and Burn
              Hazards
            </p>
            <p className="mt-0.5 text-xs text-graphite">Feb 13, 2025, similarity 0.53</p>
            <blockquote className="mt-2 border-l-2 border-rule pl-3 text-sm text-graphite">
              The lithium-ion battery in the recalled portable lamps can overheat while charging,
              posing fire and burn hazards to consumers.
            </blockquote>
          </div>
        </div>
      </div>
      <figcaption className="rounded-b-lg border-t border-rule bg-paper px-5 py-3 text-xs text-graphite">
        A real result: the 25 closest of 10,039 U.S. recalls. Bars show the share of those recalls
        with each hazard; ticks show its usual rate across all recalls.
      </figcaption>
    </figure>
  );
}
