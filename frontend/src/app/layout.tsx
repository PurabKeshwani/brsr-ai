import type { Metadata } from "next";
import { Geist, Geist_Mono, Playfair_Display } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const playfair = Playfair_Display({
  variable: "--font-playfair",
  subsets: ["latin"],
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  title: "BeyondPDF | ESG Disclosure Analysis",
  description: "Detecting greenwashing and analyzing SEBI BRSR disclosures.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${playfair.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col selection:bg-accent selection:text-accent-foreground">
        <header className="sticky top-0 z-50 glass-panel border-b-0 border-x-0 border-t-0 border-b border-border/50">
          <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
            <Link
              href="/"
              className="font-serif italic text-xl tracking-tight flex items-center gap-2"
            >
              <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
              BeyondPDF
            </Link>
            <nav className="flex items-center gap-6 text-sm font-medium text-muted-foreground">
              <Link
                href="/companies"
                className="hover:text-foreground transition-colors"
              >
                Companies
              </Link>
              <Link
                href="/compare"
                className="hover:text-foreground transition-colors"
              >
                Compare
              </Link>
              <Link
                href="/"
                className="hover:text-foreground transition-colors"
              >
                Methodology
              </Link>
              <div className="w-px h-4 bg-border/50 hidden md:block" />
              <Link
                href="/upload"
                className="px-4 py-1.5 rounded-full border border-accent/30 text-accent hover:bg-accent/10 transition-colors"
              >
                Analyze Filing
              </Link>
            </nav>
          </div>
        </header>
        <main className="flex-1 flex flex-col">{children}</main>
        <footer className="border-t border-border/50 py-12 mt-24">
          <div className="max-w-6xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between text-xs text-muted-foreground">
            <p>
              © {new Date().getFullYear()} Capstone Research Project. Data
              extracted from public SEBI BRSR filings.
            </p>
            <div className="flex gap-4 mt-4 md:mt-0">
              <span className="hover:text-foreground cursor-pointer transition-colors">
                Privacy
              </span>
              <span className="hover:text-foreground cursor-pointer transition-colors">
                Terms
              </span>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
