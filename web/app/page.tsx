import Link from "next/link";
import { NIGHT_LIGHT, SPECIMEN_ROWS, Specimen, StripRow } from "@/components/landing/specimen";
import { SiteFooter } from "@/components/site-footer";
import { EXAMPLES } from "@/lib/examples";

const tryHref = (text: string) => `/analyze?q=${encodeURIComponent(text)}`;

function Step({
  n,
  title,
  children,
  visual,
}: {
  n: number;
  title: string;
  children: React.ReactNode;
  visual: React.ReactNode;
}) {
  return (
    <li className="grid gap-5 border-t border-rule py-8 md:grid-cols-[3rem_minmax(0,1fr)_minmax(0,22rem)] md:gap-8">
      <span className="text-2xl font-light text-graphite">{n}</span>
      <div className="max-w-md">
        <h3 className="text-lg font-semibold">{title}</h3>
        <p className="mt-2 text-graphite">{children}</p>
      </div>
      <div className="rounded-md border border-rule bg-sheet p-4 text-sm">{visual}</div>
    </li>
  );
}

function SimilarityLine({ title, score }: { title: string; score: number }) {
  return (
    <li className="flex items-center justify-between gap-3">
      <span className="truncate">{title}</span>
      <span className="flex shrink-0 items-center gap-1.5 text-xs text-graphite">
        <span className="relative inline-block h-1.5 w-10 rounded-full bg-rule" aria-hidden>
          <span className="absolute inset-y-0 left-0 rounded-full bg-cobalt" style={{ width: `${(score / 0.7) * 100}%` }} />
        </span>
        {score.toFixed(2)}
      </span>
    </li>
  );
}

export default function Landing() {
  return (
    <>
      <main>
        {/* Hero: the product, shown working on the brief's example. */}
        <section className="mx-auto grid max-w-7xl items-center gap-12 px-5 pt-14 pb-20 sm:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,34rem)] lg:pt-20">
          <div>
            <h1 className="max-w-xl text-4xl font-light leading-[1.08] tracking-tight sm:text-5xl lg:text-6xl">
              See which hazards got products like yours recalled.
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-graphite">
              Describe what you are designing. SafeScale AI finds the most similar products among
              10,039 U.S. recalls, shows which hazards keep coming back compared with recalls
              overall, and links every claim to the notice behind it.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3">
              <Link href="/analyze" className="rounded-md bg-cobalt px-5 py-3 font-medium text-white dark:text-paper">
                Analyze a product
              </Link>
              <Link
                href={tryHref(NIGHT_LIGHT)}
                className="text-cobalt underline decoration-cobalt/30 underline-offset-4 hover:decoration-cobalt"
              >
                Try the night light example
              </Link>
            </div>
            <p className="mt-6 text-sm text-graphite">
              Free to use. Your description is not stored.
            </p>
          </div>
          <Specimen />
        </section>

        {/* The problem. */}
        <section className="border-y border-rule bg-sheet">
          <div className="mx-auto grid max-w-7xl gap-8 px-5 py-16 sm:px-8 md:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] md:gap-16">
            <h2 className="text-2xl font-semibold leading-snug tracking-tight">
              The lessons are public. Finding them is the hard part.
            </h2>
            <div className="max-w-2xl space-y-4 font-serif text-[1.1rem] leading-[1.75]">
              <p>
                The U.S. Consumer Product Safety Commission has published every consumer product
                recall since 1973. The failures engineers need to know about are in there: lithium
                cells that overheat while charging, dressers that tip onto children, magnets that
                work loose from toys.
              </p>
              <p>
                But the record is organized by company and date, not by what a product is made of
                or how it works. SafeScale reads it the way an engineer would ask the question:
                what went wrong in products like this one?
              </p>
            </div>
          </div>
        </section>

        {/* How it works: a real sequence, so the steps are numbered. */}
        <section id="how-it-works" className="mx-auto max-w-7xl px-5 py-20 sm:px-8">
          <h2 className="text-3xl font-light tracking-tight">How it works</h2>
          <ol className="mt-8 border-b border-rule">
            <Step n={1} title="Describe the product" visual={<p className="leading-relaxed">{NIGHT_LIGHT}</p>}>
              A few lines are enough: components, power source, materials and who will use it.
            </Step>
            <Step
              n={2}
              title="Find the closest recalls"
              visual={
                <ul className="space-y-2">
                  <SimilarityLine title="Rechargeable Portable Lamps with Lithium-Ion Batteries" score={0.53} />
                  <SimilarityLine title="LED Night Lights Recalled by Camsing Global" score={0.51} />
                  <SimilarityLine title="OSRAM SYLVANIA Recalls Portable Nightlights" score={0.51} />
                </ul>
              }
            >
              Your description is compared by meaning with every recall, so a &ldquo;USB lamp&rdquo;
              can match a &ldquo;rechargeable night light&rdquo; without sharing words. Weak matches
              are set aside rather than counted.
            </Step>
            <Step
              n={3}
              title="Compare each hazard with its usual rate"
              visual={
                <div className="space-y-4">
                  {SPECIMEN_ROWS.slice(0, 2).map((row) => (
                    <StripRow key={row.label} row={row} stacked />
                  ))}
                </div>
              }
            >
              Fire shows up in almost a third of all recalls, so &ldquo;fire is common&rdquo; tells you
              little. SafeScale shows how much more often each hazard appears in products like yours
              than in recalls overall.
            </Step>
            <Step
              n={4}
              title="Read the evidence and what to check"
              visual={
                <div>
                  <p className="font-semibold">Battery thermal behavior and cell quality</p>
                  <p className="text-xs text-graphite">13 of 25 similar recalls</p>
                  <ul className="mt-2 space-y-1">
                    <li>Review cell sourcing and the battery&apos;s protection circuitry</li>
                    <li>Consider thermal-runaway and abuse testing</li>
                  </ul>
                </div>
              }
            >
              A plain-language explanation, areas worth investigating and the standards similar
              recalls failed. Every sentence cites its recalls and is checked against them before
              you see it.
            </Step>
          </ol>
        </section>

        {/* Honesty about what the signal means: part of the product, not small print. */}
        <section className="border-y border-rule bg-sheet">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-8">
            <h2 className="max-w-2xl text-3xl font-light tracking-tight">
              What a signal tells you, and what it doesn&apos;t
            </h2>
            <div className="mt-10 grid gap-10 md:grid-cols-2 md:gap-16">
              <div>
                <h3 className="font-semibold">It tells you</h3>
                <ul className="mt-4 space-y-3 text-graphite [&>li]:relative [&>li]:pl-5 [&>li]:before:absolute [&>li]:before:left-0 [&>li]:before:top-[0.6em] [&>li]:before:size-1.5 [&>li]:before:rounded-full [&>li]:before:bg-cobalt">
                  <li>Which failures recur in recalled products like yours</li>
                  <li>How much more common they are than in recalls overall</li>
                  <li>Exactly which recall notices say so, with links to each one</li>
                  <li>Which standards those products failed</li>
                </ul>
              </div>
              <div>
                <h3 className="font-semibold">It doesn&apos;t tell you</h3>
                <ul className="mt-4 space-y-3 text-graphite [&>li]:relative [&>li]:pl-5 [&>li]:before:absolute [&>li]:before:left-0 [&>li]:before:top-[0.7em] [&>li]:before:h-0.5 [&>li]:before:w-2 [&>li]:before:bg-graphite/60">
                  <li>
                    The chance your product will fail. Recall data only contains products that had
                    problems, not the many that shipped without incident.
                  </li>
                  <li>Whether your product is safe or compliant</li>
                  <li>Anything about hazards no similar product has been recalled for</li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* Credibility through measurement. */}
        <section className="mx-auto grid max-w-7xl gap-8 px-5 py-20 sm:px-8 md:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] md:gap-16">
          <h2 className="text-2xl font-semibold leading-snug tracking-tight">Checked, not assumed</h2>
          <div className="max-w-2xl">
            <dl className="divide-y divide-rule border-y border-rule">
              <div className="grid gap-1 py-4 sm:grid-cols-[9rem_1fr] sm:gap-6">
                <dt className="font-semibold">Hazard labels</dt>
                <dd className="text-graphite">
                  Agree with a blind, hand-labeled sample of recalls with an F1 score of 0.92.
                </dd>
              </div>
              <div className="grid gap-1 py-4 sm:grid-cols-[9rem_1fr] sm:gap-6">
                <dt className="font-semibold">Explanations</dt>
                <dd className="text-graphite">
                  Validated sentence by sentence: every citation, number and word choice is checked
                  against the evidence. Anything that fails is removed.
                </dd>
              </div>
              <div className="grid gap-1 py-4 sm:grid-cols-[9rem_1fr] sm:gap-6">
                <dt className="font-semibold">Speed</dt>
                <dd className="text-graphite">
                  The hazard analysis arrives in under a second; the written explanation in about
                  nine.
                </dd>
              </div>
            </dl>
            <Link
              href="/about"
              className="mt-5 inline-block text-cobalt underline decoration-cobalt/30 underline-offset-4 hover:decoration-cobalt"
            >
              Read the methodology
            </Link>
          </div>
        </section>

        {/* Start here: a plain GET form, so it works before any JavaScript loads. */}
        <section className="bg-ink text-paper">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-8">
            <h2 className="max-w-2xl text-3xl font-light tracking-tight">Try it with what you are building</h2>
            <form action="/analyze" method="get" className="mt-8 flex max-w-3xl flex-col gap-3 sm:flex-row">
              <label htmlFor="landing-q" className="sr-only">
                Product description
              </label>
              <input
                id="landing-q"
                name="q"
                required
                minLength={10}
                maxLength={1000}
                placeholder="e.g. Folding electric bicycle with a 48 V lithium battery pack"
                className="min-w-0 flex-1 rounded-md border border-graphite/40 bg-transparent px-4 py-3 text-paper placeholder:text-paper/50 focus:border-paper focus:outline-none"
              />
              <button type="submit" className="rounded-md bg-paper px-5 py-3 font-medium text-ink">
                Analyze a product
              </button>
            </form>
            <p className="mt-6 flex flex-wrap gap-x-5 gap-y-2 text-sm text-paper/70">
              <span>Or start from an example:</span>
              {EXAMPLES.slice(1).map((ex) => (
                <Link key={ex.label} href={tryHref(ex.text)} className="underline decoration-paper/30 underline-offset-4 hover:text-paper">
                  {ex.label}
                </Link>
              ))}
            </p>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
