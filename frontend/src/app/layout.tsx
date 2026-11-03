import type { Metadata } from "next";
import localFont from "next/font/local";
import { Shell } from "@/components/workspace/Shell";
import "./globals.css";
const sans = localFont({
  src: "./fonts/geist-latin.woff2",
  variable: "--font-geist-sans",
  display: "swap",
  weight: "100 900",
});
const mono = localFont({
  src: "./fonts/geist-mono-latin.woff2",
  variable: "--font-geist-mono",
  display: "swap",
  weight: "100 900",
});
export const metadata: Metadata = {
  title: "GRASP | BRSR Research Workspace",
  applicationName: "GRASP",
  description:
    "Compare BRSR disclosures, explore transparency scores and inspect source-linked evidence.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <a href="#main-content" className="skip-link">
          Skip to analysis
        </a>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
