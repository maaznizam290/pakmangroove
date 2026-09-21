"use client";

import { useEffect, useState } from "react";
import { api, type ToolResponse } from "@/lib/api";
import LimitationsNotice from "@/components/LimitationsNotice";

interface ConditionRow {
  cell_id: number;
  condition_indicator: number;
  contributing_indices: Record<string, number>;
  stress_flag: boolean;
  label: string;
}

export default function HealthMapPage() {
  const [resp, setResp] = useState<ToolResponse<ConditionRow[]> | null>(null);

  useEffect(() => {
    api.defaultAoi().then((aoi) => api.healthIndicators(aoi.bounds)).then(setResp as never);
  }, []);

  const rows = (resp?.data as ConditionRow[] | null) || [];

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Mangrove Health Map</h1>
        <p className="text-neutral-400 text-sm mt-1">
          {rows[0]?.label ?? "REMOTE-SENSING VEGETATION / CANOPY CONDITION INDICATOR"} — a Sentinel-2-derived proxy, not a
          verified ecosystem-health measurement.
        </p>
      </div>

      {resp && <LimitationsNotice limitations={resp.limitations} />}

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
