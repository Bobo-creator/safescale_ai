import type { Metadata } from "next";
import { Public_Sans, Source_Serif_4 } from "next/font/google";
import Link from "next/link";
import { LogoMark } from "@/components/logo";
import "./globals.css";

const publicSans = Public_Sans({ variable: "--font-public-sans", subsets: ["latin"] });
const sourceSerif = Source_Serif_4({ variable: "--font-source-serif", subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL("https://safescale-ai.vercel.app"),
  title: { default: "SafeScale AI", template: "%s · SafeScale AI" },
  description:
    "Describe a product and see which hazards got similar products recalled, with the U.S. CPSC recall notices behind every claim.",
  openGraph: {
    title: "SafeScale AI",
    description: "See which hazards got products like yours recalled, before yours ships.",
    type: "website",
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${publicSans.variable} ${sourceSerif.variable} antialiased`}>
      <body className="flex min-h-dvh flex-col font-sans">
        <a
          href="#content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-sheet focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        <header className="sticky top-0 z-30 border-b border-rule bg-sheet/90 backdrop-blur">
          <nav className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-3 sm:px-8">
            <Link href="/" className="flex items-center gap-2 whitespace-nowrap text-lg font-semibold tracking-tight">
              <LogoMark />
              SafeScale AI
            </Link>
            <div className="flex items-center gap-4 text-sm sm:gap-5">
              <Link href="/about" className="text-graphite underline-offset-4 hover:text-ink hover:underline">
                Methodology
              </Link>
              <Link
                href="/analyze"
                className="whitespace-nowrap rounded-md bg-cobalt px-3.5 py-2 font-medium text-white dark:text-paper"
              >
                <span className="sm:hidden">Analyze</span>
                <span className="hidden sm:inline">Analyze a product</span>
              </Link>
            </div>
          </nav>
        </header>
        <div id="content" className="flex flex-1 flex-col">
          {children}
        </div>
      </body>
    </html>
  );
}
