import type { Metadata } from "next";
import { DISCLAIMER } from "@/lib/copy";
import { Dashboard } from "./dashboard";

export const metadata: Metadata = { title: "Analyze a product" };

export default function AnalyzePage() {
  return (
    <>
      <main className="flex-1 pb-24">
        <Dashboard />
      </main>
      {/* With results on screen, the disclaimer stays in view. */}
      <aside
        className="fixed inset-x-0 bottom-0 z-20 border-t border-rule bg-sheet/95 backdrop-blur"
        aria-label="Disclaimer"
      >
        <p className="mx-auto max-w-7xl px-5 py-3 text-xs leading-relaxed text-graphite sm:px-8">
          {DISCLAIMER}
        </p>
      </aside>
    </>
  );
}
