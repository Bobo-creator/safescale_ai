import Link from "next/link";
import { DISCLAIMER } from "@/lib/copy";
import { LogoMark } from "./logo";

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-rule bg-sheet">
      <div className="mx-auto grid max-w-7xl gap-6 px-5 py-10 text-sm text-graphite sm:grid-cols-[1fr_auto] sm:px-8">
        <div className="max-w-xl space-y-3">
          <p className="flex items-center gap-2 font-semibold text-ink">
            <LogoMark className="size-4" /> SafeScale AI
          </p>
          <p>{DISCLAIMER}</p>
          <p>
            Data: U.S. Consumer Product Safety Commission recall notices, 1973 to 2026, from the
            public SaferProducts.gov API.
          </p>
        </div>
        <nav className="flex flex-col gap-2 sm:items-end" aria-label="Footer">
          <Link href="/analyze" className="hover:text-ink">Analyze a product</Link>
          <Link href="/about" className="hover:text-ink">Methodology</Link>
        </nav>
      </div>
    </footer>
  );
}
