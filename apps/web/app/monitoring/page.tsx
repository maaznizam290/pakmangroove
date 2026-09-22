"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import LimitationsNotice from "@/components/LimitationsNotice";
import ErrorBanner from "@/components/ErrorBanner";

interface ModelRow {
  model_id: string;
  task: string;
  version: string;
  algorithm: string;
  metrics: Record<string, unknown>;
  promoted: boolean;
  is_synthetic: boolean;
  trained_at: string;
}

interface ReviewRow {
  review_id: string;
  cell_id: number;
  reason: string;
  confidence: number | null;
  status: string;
  created_at: string;
}

export default function MonitoringPage() {
  const [models, setModels] = useState<ModelRow[]>([]);
  const [modelLimitations, setModelLimitations] = useState<string[]>([]);
  const [modelError, setModelError] = useState<string | null>(null);
  const [queue, setQueue] = useState<ReviewRow[]>([]);
  const [queueError, setQueueError] = useState<string | null>(null);

  useEffect(() => {
    api
      .models()
      .then((r) => {
        setModels(r.data as ModelRow[]);
        setModelLimitations(r.limitations);
      })
      .catch((e) => setModelError(String(e)));
    api.reviewQueue<ReviewRow>().then(setQueue).catch((e) => setQueueError(String(e)));
  }, []);

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Model Monitoring</h1>
        <p className="text-neutral-400 text-sm mt-1">
          Registered model versions and the active-learning review queue. Promotion is human-gated — Hermes and the
          retrain job may register a candidate but can never flip it to promoted.
        </p>
      </div>

      <div className="space-y-2">
        <h2 className="text-sm font-medium text-neutral-300 mb-2">Model registry</h2>
        <ErrorBanner message={modelError} />
        <LimitationsNotice limitations={modelLimitations} />
        {models.length ? (
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-neutral-800 text-neutral-400 text-left">
                <th className="py-2 pr-4">Task</th>
                <th className="py-2 pr-4">Version</th>
                <th className="py-2 pr-4">Algorithm</th>
                <th className="py-2 pr-4">Metrics</th>
                <th className="py-2">Promoted</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m) => (
                <tr key={m.model_id} className="border-b border-neutral-900">
                  <td className="py-2 pr-4">
                    {m.task}
                    {m.is_synthetic && (
                      <span className="ml-2 text-[10px] uppercase tracking-wide bg-amber-950 text-amber-400 border border-amber-800 rounded px-1.5 py-0.5">
                        smoke test only
                      </span>
                    )}
                  </td>
                  <td className="py-2 pr-4">{m.version}</td>
                  <td className="py-2 pr-4">{m.algorithm}</td>
                  <td className="py-2 pr-4 text-neutral-400 text-xs">{JSON.stringify(m.metrics)}</td>
                  <td className="py-2">{m.promoted ? <span className="text-emerald-400">yes</span> : <span className="text-neutral-500">no</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="text-neutral-500 text-sm">No models registered yet.</div>
        )}
      </div>

      <div>
        <h2 className="text-sm font-medium text-neutral-300 mb-2">Review queue (pending)</h2>
        <ErrorBanner message={queueError} />
        {queue.length ? (
          <ul className="space-y-2">
            {queue.map((q) => (
              <li key={q.review_id} className="bg-neutral-900 border border-neutral-800 rounded p-3 text-sm flex justify-between">
                <span>Cell {q.cell_id} — {q.reason.replaceAll("_", " ")}</span>
                <span className="text-neutral-500 text-xs">{q.confidence != null ? `conf ${q.confidence.toFixed(2)}` : ""}</span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-neutral-500 text-sm">Review queue is empty.</div>
        )}
      </div>
    </div>
  );
}
