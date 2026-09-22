"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import ErrorBanner from "@/components/ErrorBanner";

interface SourceRow {
  id: string;
  category: string;
  title: string;
  authors: string | null;
  year: number | null;
  doi: string | null;
  source_url: string | null;
  status: string;
}

const STATUS_STYLE: Record<string, string> = {
  ingested: "bg-emerald-950 text-emerald-400 border-emerald-800",
  not_yet_uploaded: "bg-neutral-800 text-neutral-400 border-neutral-700",
  needs_validation: "bg-red-950 text-red-400 border-red-800",
};

export default function EvidencePage() {
  const [rows, setRows] = useState<SourceRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.ragSources<SourceRow>().then(setRows).catch((e) => setError(String(e)));
  }, []);

  const byCategory = rows.reduce<Record<string, SourceRow[]>>((acc, r) => {
    (acc[r.category] ??= []).push(r);
    return acc;
  }, {});

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Evidence / Sources</h1>
        <p className="text-neutral-400 text-sm mt-1">
          Mangrove_AI_Knowledge registry. Every citation Hermes/RAG can produce traces back to one of these rows —
          nothing not listed here is ever cited.
        </p>
      </div>

      <ErrorBanner message={error} />

      {Object.entries(byCategory).sort().map(([category, sources]) => (
        <div key={category}>
          <h2 className="text-sm font-medium text-neutral-300 mb-2">{category.replaceAll("_", " ")}</h2>
          <ul className="space-y-2">
            {sources.map((s) => (
              <li key={s.id} className="bg-neutral-900 border border-neutral-800 rounded p-3 text-sm flex justify-between gap-3">
                <div>
                  <div className="font-medium">{s.title}</div>
                  <div className="text-neutral-500 text-xs mt-0.5">
                    {s.authors || "authors unknown"} {s.year ? `· ${s.year}` : ""} {s.doi ? `· DOI ${s.doi}` : ""}
                  </div>
                </div>
                <span className={`shrink-0 h-fit px-2 py-0.5 rounded border text-xs ${STATUS_STYLE[s.status] || STATUS_STYLE.not_yet_uploaded}`}>
                  {s.status.replaceAll("_", " ")}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
