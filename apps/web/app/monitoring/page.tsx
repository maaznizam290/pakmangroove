"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface ModelRow {
  model_id: string;
  task: string;
  version: string;
  algorithm: string;
  metrics: Record<string, unknown>;
  promoted: boolean;
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
  const [queue, setQueue] = useState<ReviewRow[]>([]);

  useEffect(() => {
    api.models().then((r) => setModels(r.data as ModelRow[]));
    api.reviewQueue<ReviewRow>().then(setQueue);
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

      <div>
        <h2 className="text-sm font-medium text-neutral-300 mb-2">Model registry</h2>
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
                  <td className="py-2 pr-4">{m.task}</td>
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
