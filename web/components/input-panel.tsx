"use client";

import { useId, useState } from "react";
import { EXAMPLES } from "@/lib/examples";
import type { Depth, Method, Query } from "@/lib/types";

const DEPTHS: Depth[] = [25, 50, 100];
const METHODS: { value: Method; label: string; hint: string }[] = [
  { value: "vector", label: "Meaning", hint: "Embedding similarity (default)" },
  { value: "keyword", label: "Keywords", hint: "Full-text word match" },
  { value: "hybrid", label: "Both", hint: "Rank fusion of the two" },
];

export function InputPanel({
  busy,
  onSubmit,
}: {
  busy: boolean;
  onSubmit: (q: Query) => void;
}) {
  const [query, setQuery] = useState("");
  const [k, setK] = useState<Depth>(25);
  const [method, setMethod] = useState<Method>("vector");
  const textId = useId();
  const length = query.trim().length;
  const valid = length >= 10 && length <= 1000;

  return (
    <form
      className="mx-auto max-w-7xl px-5 pt-10 pb-8 sm:px-8 sm:pt-14"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid && !busy) onSubmit({ query: query.trim(), k, method });
      }}
    >
      <label htmlFor={textId} className="block max-w-3xl text-3xl font-light leading-tight tracking-tight sm:text-4xl">
        Describe the product you are designing
      </label>
      <p className="mt-3 max-w-2xl text-graphite">
        Components, power source, materials and who uses it. SafeScale finds similar products in
        10,039 U.S. recalls and shows which hazards keep coming back.
      </p>

      <textarea
        id={textId}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && valid && !busy) {
            onSubmit({ query: query.trim(), k, method });
          }
        }}
        rows={3}
        maxLength={1000}
        placeholder="e.g. Rechargeable children's night light with a 2000 mAh lithium-ion battery and USB-C charging"
        className="mt-6 block w-full max-w-4xl resize-y rounded-md border border-rule bg-sheet px-4 py-3 text-lg leading-relaxed shadow-[inset_0_1px_0_rgba(27,37,51,0.04)] placeholder:text-graphite/70 focus:border-cobalt focus:outline-none"
      />

      <div className="mt-3 flex max-w-4xl flex-wrap items-baseline gap-x-3 gap-y-2 text-sm">
        <span className="text-graphite">Try</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex.label}
            type="button"
            onClick={() => setQuery(ex.text)}
            className="text-cobalt underline decoration-cobalt/30 underline-offset-4 hover:decoration-cobalt"
          >
            {ex.label}
          </button>
        ))}
      </div>

      <div className="mt-6 flex max-w-4xl flex-wrap items-center gap-x-8 gap-y-4">
        <button
          type="submit"
          disabled={!valid || busy}
          className="rounded-md bg-cobalt px-5 py-2.5 font-medium text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-50 dark:text-paper"
        >
          {busy ? "Analyzing…" : "Analyze hazards"}
        </button>

        <fieldset className="flex items-center gap-3 text-sm">
          <legend className="sr-only">Number of similar recalls</legend>
          <span className="text-graphite" aria-hidden>
            Compare with
          </span>
          <div className="flex overflow-hidden rounded-md border border-rule">
            {DEPTHS.map((d) => (
              <label
                key={d}
                className="cursor-pointer px-3 py-1.5 has-checked:bg-cobalt-soft has-checked:font-medium has-checked:text-cobalt has-focus-visible:outline-2 has-focus-visible:outline-cobalt"
              >
                <input
                  type="radio"
                  name="k"
                  value={d}
                  checked={k === d}
                  onChange={() => setK(d)}
                  className="sr-only"
                />
                {d}
              </label>
            ))}
          </div>
          <span className="text-graphite" aria-hidden>
            similar recalls
          </span>
        </fieldset>

        <details className="text-sm">
          <summary className="cursor-pointer text-graphite">Advanced</summary>
          <fieldset className="mt-2 flex flex-wrap gap-4">
            <legend className="sr-only">Search method</legend>
            {METHODS.map((m) => (
              <label key={m.value} className="flex cursor-pointer items-center gap-2" title={m.hint}>
                <input
                  type="radio"
                  name="method"
                  value={m.value}
                  checked={method === m.value}
                  onChange={() => setMethod(m.value)}
                  className="accent-cobalt"
                />
                {m.label}
                <span className="text-graphite">({m.hint.toLowerCase()})</span>
              </label>
            ))}
          </fieldset>
        </details>
      </div>

      <p className="mt-5 max-w-4xl text-xs text-graphite">
        Your description is sent to OpenAI to find similar recalls and write the explanation. It is
        not stored.{" "}
        {length > 0 && length < 10 && <span className="text-high">Add a few more words.</span>}
      </p>
    </form>
  );
}
