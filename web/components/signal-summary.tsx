import { SIGNAL_STYLES, SIGNAL_WORDS, categoryLabel, joinLabels } from "@/lib/format";
import type { HazardReport } from "@/lib/types";

export function SignalSummary({ report }: { report: HazardReport }) {
  if (report.insufficient_evidence) {
    return (
      <section aria-labelledby="signal-heading">
        <h2 id="signal-heading" className="text-2xl font-semibold tracking-tight">
          Not enough similar recalls to judge
        </h2>
        <p className="mt-2 max-w-2xl text-graphite">
          Only {report.relevant} of the {report.matches.length} closest recalls are similar enough
          to count. That says the recall record has little to compare against. It does not mean the
          product has no hazards. Try describing its parts, power source and users in more detail.
        </p>
      </section>
    );
  }
  const style = SIGNAL_STYLES[report.overall_signal];
  const drivers = joinLabels(report.signal_drivers.map((c) => categoryLabel(c).toLowerCase()));
  return (
    <section aria-labelledby="signal-heading">
      <p className={`inline-flex items-center gap-2 rounded px-2.5 py-1 text-sm font-semibold ${style.bg} ${style.text}`}>
        <span className={`inline-block size-2 rounded-full ${style.bar}`} aria-hidden />
        {SIGNAL_WORDS[report.overall_signal]} historical signal
      </p>
      <h2 id="signal-heading" className="mt-3 max-w-3xl text-2xl font-semibold leading-snug tracking-tight sm:text-3xl">
        {drivers
          ? `${drivers.charAt(0).toUpperCase()}${drivers.slice(1)} ${report.signal_drivers.length > 1 ? "recur" : "recurs"} in similar recalls`
          : "No hazard stands out among similar recalls"}
      </h2>
      <p className="mt-2 text-graphite">
        Based on {report.relevant} of the {report.matches.length} closest recalls. A ranked signal
        from past recalls, not a probability that this product will fail.
      </p>
    </section>
  );
}
