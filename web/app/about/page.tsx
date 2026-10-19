import type { Metadata } from "next";
import Link from "next/link";
import { CATEGORY_LABELS } from "@/lib/format";

export const metadata: Metadata = { title: "How it works · SafeScale AI" };

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-12">
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      <div className="mt-3 space-y-4 font-serif text-[1.07rem] leading-[1.75]">{children}</div>
    </section>
  );
}

export default function About() {
  return (
    <main className="mx-auto max-w-3xl px-5 py-14 sm:px-8">
      <h1 className="text-3xl font-light leading-tight tracking-tight sm:text-4xl">How SafeScale AI works</h1>
      <p className="mt-4 text-lg text-graphite">
        It compares a product you are designing with every product the U.S. Consumer Product Safety
        Commission has recalled, and shows which hazards keep coming back in the closest matches.
      </p>

      <Section title="The data">
        <p>
          10,039 recall notices from the CPSC&apos;s public recall database, from 1973 to
          2026. Each notice describes the product, what went wrong and the hazard it posed. Every
          result links back to the original notice.
        </p>
      </Section>

      <Section title="Finding similar products">
        <p>
          Your description and every recall are turned into embeddings (OpenAI
          text-embedding-3-small), numerical fingerprints of meaning, so a &ldquo;USB-rechargeable
          lamp&rdquo; can match a &ldquo;lithium-ion night light&rdquo; without sharing words.
          SafeScale takes the 25, 50 or 100 closest recalls. Recalls with a similarity below 0.30
          are shown as weak matches but never counted. Under Advanced you can switch to plain keyword
          matching, or a blend of both, to compare methods.
        </p>
      </Section>

      <Section title="Labeling hazards">
        <p>
          Each recall is labeled with one or more of twelve hazard categories by rules over its
          hazard description, and every label keeps the phrase that triggered it. On a blind sample
          of 50 recalls labeled by hand, the labels scored an F1 of 0.92.
        </p>
        <p className="font-sans text-base text-graphite">{Object.values(CATEGORY_LABELS).join(", ")}.</p>
      </Section>

      <Section title="What the signal means">
        <p>
          For each hazard, SafeScale counts how many of the similar recalls involved it and compares
          that share with its usual rate across all recalls. A hazard is rated high when it appears
          in at least 40% of similar recalls, in at least 5 of them, and at 1.5 times its usual rate
          or more; moderate at 20% and 3 recalls. The overall signal is the highest of these.
        </p>
        <p>
          It is a ranked signal from history, not a probability. Recall data only contains products
          that had problems; the many similar products that shipped without incident are not in it.
          A high signal says engineers have seen this failure before in products like yours. A low
          signal does not say your product is safe.
        </p>
      </Section>

      <Section title="The written explanation">
        <p>
          A language model (OpenAI gpt-6-luna) writes the explanation using only the matched
          recalls. Before anything is shown, every sentence is checked: it must cite recalls from
          the evidence, the cited recalls must support that specific claim, every number must
          appear in the data, and safety or compliance verdicts are not allowed. Sentences that fail
          are removed. If too many fail, a summary built directly from the data is shown instead.
        </p>
      </Section>

      <Section title="Your description">
        <p>
          It is sent to OpenAI to compute the embedding and write the explanation. SafeScale does
          not store it or log it.
        </p>
      </Section>

      <p className="mt-14">
        <Link href="/" className="text-cobalt underline decoration-cobalt/30 underline-offset-4 hover:decoration-cobalt">
          Analyze a product
        </Link>
      </p>
    </main>
  );
}
