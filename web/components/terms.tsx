import type { Term } from "@/lib/types";

function TermRow({ title, terms }: { title: string; terms: Term[] }) {
  if (!terms.length) return null;
  return (
    <div>
      <h4 className="text-sm font-semibold">{title}</h4>
      <p className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
        {terms.map((t) => (
          <span key={t.term}>
            {t.term} <span className="text-sm text-graphite">{t.matches}</span>
          </span>
        ))}
      </p>
    </div>
  );
}

export function Terms({ shared, failure }: { shared: Term[]; failure: Term[] }) {
  if (!shared.length && !failure.length) return null;
  return (
    <section aria-label="Recurring terms" className="mt-8 grid gap-5 sm:grid-cols-2">
      <TermRow title="Shared with your description" terms={shared} />
      <TermRow title="Recurring in what failed" terms={failure} />
    </section>
  );
}
