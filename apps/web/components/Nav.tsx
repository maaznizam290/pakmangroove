"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const PAGES = [
  { href: "/", label: "Dashboard" },
  { href: "/ai-research", label: "AI Research" },
  { href: "/satellite", label: "Satellite Explorer" },
  { href: "/detection-map", label: "Detection Map" },
  { href: "/health-map", label: "Health Map" },
  { href: "/suitability-map", label: "Restoration Suitability" },
  { href: "/timeline", label: "Historical Timeline" },
  { href: "/species", label: "Species Explorer" },
  { href: "/evidence", label: "Evidence / Sources" },
  { href: "/monitoring", label: "Model Monitoring" },
];

export default function Nav() {
  const pathname = usePathname();
  return (
    <nav className="border-b border-neutral-800 bg-neutral-950 text-neutral-100 px-4 py-2 flex flex-wrap gap-1 sticky top-0 z-50">
      <span className="font-semibold text-emerald-400 mr-4 py-1.5 shrink-0">Mangrove AI Intelligence</span>
      {PAGES.map((p) => (
        <Link
          key={p.href}
          href={p.href}
          className={`px-3 py-1.5 rounded text-sm whitespace-nowrap ${
            pathname === p.href ? "bg-emerald-700 text-white" : "text-neutral-300 hover:bg-neutral-800"
          }`}
        >
          {p.label}
        </Link>
      ))}
    </nav>
  );
}
