import type { Metadata } from "next";
import { Public_Sans, Source_Serif_4 } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const publicSans = Public_Sans({ variable: "--font-public-sans", subsets: ["latin"] });
const sourceSerif = Source_Serif_4({ variable: "--font-source-serif", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "SafeScale AI",
  description:
    "Describe a product and see which hazards recur in similar U.S. CPSC recalls, with the evidence behind every claim.",
};

const DISCLAIMER =
  "SafeScale AI does not certify that a product is safe or compliant. It identifies historically supported hazard signals and evidence that engineers should investigate further.";

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${publicSans.variable} ${sourceSerif.variable} antialiased`}>
      <body className="flex min-h-dvh flex-col font-sans">
        <header className="border-b border-rule bg-sheet">
          <nav className="mx-auto flex max-w-7xl items-baseline justify-between px-5 py-4 sm:px-8">
            <Link href="/" className="text-lg font-semibold tracking-tight">
              SafeScale AI
            </Link>
            <Link href="/about" className="text-sm text-graphite underline-offset-4 hover:underline">
              How it works
            </Link>
          </nav>
        </header>
        <div className="flex-1 pb-24">{children}</div>
        <footer
          className="fixed inset-x-0 bottom-0 z-20 border-t border-rule bg-sheet/95 backdrop-blur"
          aria-label="Disclaimer"
        >
          <p className="mx-auto max-w-7xl px-5 py-3 text-xs leading-relaxed text-graphite sm:px-8">
            {DISCLAIMER}
          </p>
        </footer>
      </body>
    </html>
  );
}
