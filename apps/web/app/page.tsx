"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Dashboard() {
  const [modelCount, setModelCount] = useState<number | null>(null);
  const [reviewCount, setReviewCount] = useState<number | null>(null);
  const [sourcesIngested, setSourcesIngested] = useState<{ total: number; ingested: number } | null>(null);

  useEffect(() => {
    api.models().then((r) => setModelCount((r.data as unknown[]).length)).catch(() => setModelCount(0));
    api.reviewQueue().then((r) => setReviewCount(r.length)).catch(() => setReviewCount(0));
    api.ragSources().then((rows) => {
      const ingested = rows.filter((r) => r.status === "ingested").length;
      setSourcesIngested({ total: rows.length, ingested });
    }).catch(() => setSourcesIngested({ total: 0, ingested: 0 }));
  }, []);

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Mangrove AI Intelligence</h1>
        <p className="text-neutral-400 mt-1">
          Predictive coastal risk & restoration intelligence for the Karachi coast / Bundal / Indus Delta.
          Hermes orchestrates Sentinel-2, GMW, CGMD, GBIF, and the Mangrove_AI_Knowledge RAG corpus into a
          Restoration Suitability assessment — every candidate area is labeled{" "}
          <span className="text-amber-400 font-medium">“Candidate only — field validation required.”</span>
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatTile label="Registered models" value={modelCount} />
        <StatTile label="Pending review-queue tiles" value={reviewCount} />
        <StatTile
          label="RAG sources ingested"
          value={sourcesIngested ? `${sourcesIngested.ingested} / ${sourcesIngested.total}` : null}
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <NavCard href="/suitability-map" title="Restoration Suitability Map" desc="The central output — click any candidate cell for score, confidence, reasons, and citations." />
        <NavCard href="/ai-research" title="AI Research" desc="Ask Hermes: “Show me where mangrove restoration may be suitable and explain why.”" />
        <NavCard href="/detection-map" title="Mangrove Detection Map" desc="Current mangrove probability from the RF/GBM classifier." />
        <NavCard href="/timeline" title="Historical Timeline" desc="1984–2023 extent gain/loss from CGMD-Extent30." />
        <NavCard href="/evidence" title="Evidence / Sources" desc="Every cited source's status — ingested vs. not yet uploaded." />
        <NavCard href="/monitoring" title="Model Monitoring" desc="Model registry, metrics, promotion history, review queue." />
      </div>
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: number | string | null }) {
  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
      <div className="text-neutral-400 text-xs uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value ?? "…"}</div>
    </div>
  );
}

function NavCard({ href, title, desc }: { href: string; title: string; desc: string }) {
  return (
    <Link href={href} className="block bg-neutral-900 border border-neutral-800 rounded-lg p-4 hover:border-emerald-700 transition-colors">
      <div className="font-medium text-emerald-400">{title}</div>
      <div className="text-neutral-400 text-sm mt-1">{desc}</div>
    </Link>
  );
}
