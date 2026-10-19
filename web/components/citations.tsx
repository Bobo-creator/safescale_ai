"use client";

import { useEvidence } from "./evidence-context";

/** Inline citations as the evidence cards' numbers: "[3, 7]". Each number jumps to its card. */
export function Citations({ ids }: { ids: number[] }) {
  const { rankOf, focus } = useEvidence();
  if (!ids.length) return null;
  return (
    <span className="whitespace-nowrap font-sans text-[0.8em] text-cobalt">
      [
      {ids.map((id, i) => {
        const rank = rankOf(id);
        return (
          <span key={id}>
            {i > 0 && ", "}
            <button
              type="button"
              onClick={() => focus(id)}
              className="underline decoration-cobalt/40 underline-offset-2 hover:decoration-cobalt"
              aria-label={`Show similar recall ${rank ?? id}`}
            >
              {rank ?? `#${id}`}
            </button>
          </span>
        );
      })}
      ]
    </span>
  );
}
