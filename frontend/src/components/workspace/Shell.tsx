"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Building2,
  Columns3,
  ChartNoAxesCombined,
  Upload,
  BookOpen,
  ArrowUpRight,
  Search,
} from "lucide-react";
import { useEffect, useRef } from "react";

const routes = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/companies", label: "Company explorer", icon: Building2 },
  { href: "/compare", label: "Compare", icon: Columns3 },
  { href: "/time-series", label: "Time series", icon: ChartNoAxesCombined },
  { href: "/upload", label: "Analyze filing", icon: Upload },
  { href: "/methodology", label: "Methodology", icon: BookOpen },
];
export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname(),
    router = useRouter();
  const finishTransition = useRef<(() => void) | null>(null);
  useEffect(() => {
    finishTransition.current?.();
    finishTransition.current = null;
  }, [path]);
  useEffect(() => {
    // Exit runs on the old document; the destination enters through template.tsx.
    const navigate = (event: MouseEvent) => {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      )
        return;
      const a = (event.target as Element).closest(
        "a",
      ) as HTMLAnchorElement | null;
      if (
        !a ||
        a.target ||
        a.download ||
        a.origin !== location.origin ||
        a.pathname === location.pathname ||
        !document.startViewTransition ||
        matchMedia("(prefers-reduced-motion: reduce)").matches
      )
        return;
      event.preventDefault();
      document.startViewTransition(
        () =>
          new Promise<void>((resolve) => {
            finishTransition.current?.();
            finishTransition.current = resolve;
            router.push(a.pathname + a.search + a.hash);
            setTimeout(resolve, 2000);
          }),
      );
    };
    document.addEventListener("click", navigate, true);
    return () => document.removeEventListener("click", navigate, true);
  }, [router]);
  const current =
    routes.find((r) =>
      r.href === "/" ? path === "/" : path.startsWith(r.href),
    )?.label ?? "Company detail";
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" href="/">
          <svg viewBox="0 0 24 28" width="25" height="29" aria-hidden="true">
            <path
              d="M3 3h10l8 8v14H3z"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            />
            <path
              d="M7 19l4-5 3 2 4-6"
              fill="none"
              stroke="var(--accent)"
              strokeWidth="2"
            />
          </svg>
          <span>
            GRASP<small>BRSR intelligence</small>
          </span>
        </Link>
        <div className="workspace-scope">
          <span className="status-dot" />
          Research workspace<small>Indian listed companies</small>
        </div>
        <p className="nav-label">Analysis</p>
        <nav aria-label="Main navigation">
          {routes.map((r) => (
            <Link
              key={r.href}
              href={r.href}
              aria-current={
                (r.href === "/" ? path === "/" : path.startsWith(r.href))
                  ? "page"
                  : undefined
              }
            >
              <r.icon size={16} />
              {r.label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="method-mark">GRASP</div>
          <p>
            From filed claims
            <br />
            to traceable evidence.
          </p>
          <Link href="/methodology">
            Score methodology <ArrowUpRight size={14} />
          </Link>
          <small>Public SEBI BRSR filings</small>
        </div>
      </aside>
      <div className="app-content">
        <div className="workspace-bar">
          <span>
            Research workspace <span className="breadcrumb-slash">/</span>{" "}
            <strong>{current}</strong>
          </span>
          <Link href="/companies">
            <Search size={14} />
            Find a company <span className="kbd">Explorer</span>
          </Link>
        </div>
        <main id="main-content" className="workspace-sheet">
          {children}
        </main>
        <footer className="workspace-footer">
          <span>Disclosure quality analysis · source-linked XBRL evidence</span>
          <span>Research snapshot · scores out of 100</span>
        </footer>
      </div>
    </div>
  );
}
