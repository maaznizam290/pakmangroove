"use client";

import { useState } from "react";
import { api, type Bbox, type NamedAoi, type ToolResponse } from "@/lib/api";
import LimitationsNotice from "@/components/LimitationsNotice";
import AoiSelector from "@/components/AoiSelector";

interface ConditionRow {
  cell_id: number;
  condition_indicator: number;
  contributing_indices: Record<string, number>;
  stress_flag: boolean;
  label: string;
}

export default function HealthMapPage() {
  const [resp, setResp] = useState<ToolResponse<ConditionRow[]> | null>(null);
  const [aoi, setAoi] = useState<NamedAoi | null>(null);

  const handleAoiChange = (bounds: Bbox, selected: NamedAoi | null) => {
    setAoi(selected);
    setResp(null);
    api.healthIndicators(bounds).then(setResp as never);
  };

  const rows = (resp?.data as ConditionRow[] | null) || [];

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Mangrove Health Map</h1>
          <p className="text-neutral-400 text-sm mt-1">
            {rows[0]?.label ?? "REMOTE-SENSING VEGETATION / CANOPY CONDITION INDICATOR"} — a Sentinel-2-derived proxy, not a
            verified ecosystem-health measurement.
          </p>
          {aoi && <p className="text-neutral-500 text-xs mt-1">{aoi.name}{aoi.description ? ` — ${aoi.description}` : ""}</p>}
        </div>
        <AoiSelector onChange={handleAoiChange} />
      </div>

      {resp && <LimitationsNotice limitations={resp.limitations} />}

      {resp && rows.length > 0 && (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-3 text-xs text-neutral-400 grid grid-cols-2 sm:grid-cols-4 gap-2">
          <div>
            <div className="uppercase tracking-wide text-neutral-500">Dataset</div>
            <div className="text-neutral-300">{resp.source.join(", ")}</div>
          </div>
          <div>
            <div className="uppercase tracking-wide text-neutral-500">AOI</div>
            <div className="text-neutral-300">{aoi?.name ?? "default"}</div>
          </div>
          <div>
            <div className="uppercase tracking-wide text-neutral-500">Processed</div>
            <div className="text-neutral-300">{new Date(resp.timestamp).toLocaleString()}</div>
          </div>
          <div>
            <div className="uppercase tracking-wide text-neutral-500">Classification</div>
            <div className="text-neutral-300">DERIVED (remote-sensing indicator, not a direct observation)</div>
          </div>
        </div>
      )}

      {rows.length > 0 ? (
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-neutral-800 text-neutral-400 text-left">
              <th className="py-2 pr-4">Cell</th>
              <th className="py-2 pr-4">Condition Indicator</th>
              <th className="py-2 pr-4">Stress</th>
              <th className="py-2">Contributing indices</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.cell_id} className="border-b border-neutral-900">
                <td className="py-2 pr-4">{r.cell_id}</td>
                <td className="py-2 pr-4">{r.condition_indicator.toFixed(3)}</td>
                <td className="py-2 pr-4">{r.stress_flag ? <span className="text-red-400">stressed</span> : <span className="text-emerald-400">ok</span>}</td>
                <td className="py-2 text-neutral-400">
                  {Object.entries(r.contributing_indices).map(([k, v]) => `${k}=${v.toFixed(2)}`).join(", ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        !resp && <div className="text-neutral-500">Loading…</div>
      )}
    </div>
  );
}
