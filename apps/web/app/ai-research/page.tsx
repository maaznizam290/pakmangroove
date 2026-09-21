"use client";

import { useState } from "react";
import { api } from "@/lib/api";

interface HermesAnswer {
  answer?: {
    observed_data: string[];
    derived_analysis: string[];
    scientific_evidence: { doc_id: string; title: string; page: number | null; quote: string }[];
    model_output: string[];
    limitations: string[];
  };
  candidate_count?: number;
  planner_mode?: string;
  field_validation_statement?: string;
}

const SUGGESTED = "Show me where mangrove restoration may be suitable around Karachi and explain why.";

export default function AiResearchPage() {
  const [question, setQuestion] = useState(SUGGESTED);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<HermesAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function ask() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.hermesAsk(question);
      setResult(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-4">
      <div>
        <h1 className="text-xl font-semibold">AI Research — Hermes</h1>
        <p className="text-neutral-400 text-sm mt-1">
          Hermes calls the same 15 tools the rest of this app uses — it never invents a coordinate, extent value, or
          accuracy figure itself.
        </p>
      </div>

      <div className="flex gap-2">
        <input
          className="flex-1 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button
          onClick={ask}
          disabled={loading}
          className="bg-emerald-700 hover:bg-emerald-600 disabled:opacity-50 px-4 py-2 rounded text-sm font-medium"
        >
          {loading ? "Running…" : "Ask"}
        </button>
      </div>

      {error && <div className="text-red-400 text-sm">{error}</div>}

      {result && (
        <div className="space-y-4">
          <div className="text-xs text-neutral-500">
            planner_mode: {result.planner_mode} · candidates found: {result.candidate_count ?? 0}
          </div>

          {result.answer && (
            <>
              <Section title="OBSERVED DATA" items={result.answer.observed_data} />
              <Section title="DERIVED ANALYSIS" items={result.answer.derived_analysis} />
              <div>
                <div className="text-neutral-400 text-xs uppercase tracking-wide mb-1">Scientific Evidence</div>
                {result.answer.scientific_evidence.length ? (
                  <ul className="space-y-2">
                    {result.answer.scientific_evidence.map((c, i) => (
                      <li key={i} className="bg-neutral-900 border border-neutral-800 rounded p-2 text-sm">
                        <div className="font-medium">{c.title} {c.page ? `p.${c.page}` : ""}</div>
                        <div className="text-neutral-400 text-xs mt-1">{c.quote}</div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="text-neutral-500 text-sm">Insufficient evidence in the indexed scientific sources.</div>
                )}
              </div>
              <Section title="MODEL OUTPUT" items={result.answer.model_output} />
              <Section title="LIMITATIONS" items={result.answer.limitations} tone="amber" />
            </>
          )}

          {result.field_validation_statement && (
            <div className="bg-red-950 border border-red-700 rounded px-3 py-2 text-red-300 font-medium text-sm">
              {result.field_validation_statement}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Section({ title, items, tone }: { title: string; items: string[]; tone?: "amber" }) {
  return (
    <div>
      <div className={`text-xs uppercase tracking-wide mb-1 ${tone === "amber" ? "text-amber-500" : "text-neutral-400"}`}>{title}</div>
      <ul className="list-disc list-inside text-sm space-y-0.5">
        {items.length ? items.map((it, i) => <li key={i}>{it}</li>) : <li className="text-neutral-600">none</li>}
      </ul>
    </div>
  );
}
