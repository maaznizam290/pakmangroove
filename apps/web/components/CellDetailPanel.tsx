"use client";

import type { SuitabilityCell } from "@/lib/api";

const CLASSIFICATION_COLOR: Record<string, string> = {
  VERY_HIGH: "text-emerald-400",
  HIGH: "text-emerald-500",
  MEDIUM: "text-yellow-400",
  LOW: "text-orange-400",
  EXCLUDED: "text-neutral-500",
};

export default function CellDetailPanel({ cell, onClose }: { cell: SuitabilityCell; onClose: () => void }) {
  const needsValidation = cell.classification === "HIGH" || cell.classification === "VERY_HIGH";

  return (
    <div className="absolute top-4 right-4 w-80 bg-neutral-900 border border-neutral-700 rounded-lg shadow-xl p-4 text-sm space-y-3 z-20">
      <div className="flex justify-between items-start">
        <div>
          <div className="text-xs text-neutral-400">Cell #{cell.cell_id}</div>
          <div className="text-xs text-neutral-500">{cell.lat.toFixed(5)}, {cell.lon.toFixed(5)}</div>
        </div>
        <button onClick={onClose} className="text-neutral-400 hover:text-white text-lg leading-none">×</button>
      </div>

      <div>
        <div className="text-neutral-400 text-xs uppercase tracking-wide">Suitability</div>
        <div className={`text-lg font-semibold ${CLASSIFICATION_COLOR[cell.classification]}`}>{cell.classification}</div>
      </div>

      <div>
        <div className="text-neutral-400 text-xs uppercase tracking-wide">Confidence</div>
        <div>{cell.confidence.toFixed(2)}</div>
      </div>

      <div>
        <div className="text-neutral-400 text-xs uppercase tracking-wide">Reasons</div>
        <ul className="list-disc list-inside space-y-0.5">
          {cell.reason_codes.length ? cell.reason_codes.map((r) => <li key={r}>{r.replaceAll("_", " ").toLowerCase()}</li>) : <li className="text-neutral-500">none</li>}
        </ul>
      </div>

      <div>
        <div className="text-neutral-400 text-xs uppercase tracking-wide">Data</div>
        <div>{cell.data_sources.length ? cell.data_sources.join(", ") : "none ingested yet"}</div>
      </div>

      {cell.local_ecological_risk_evidence && (
        <div className="bg-amber-950 border border-amber-700 rounded px-2 py-1 text-amber-300 text-xs">
          LOCAL ECOLOGICAL RISK EVIDENCE AVAILABLE — see Evidence / Sources for the Bundal Island sampled points near this cell.
        </div>
      )}

      <div>
        <div className="text-neutral-400 text-xs uppercase tracking-wide">Model</div>
        <div>{cell.model_version}</div>
      </div>

      {needsValidation && (
        <div className="bg-red-950 border border-red-700 rounded px-2 py-2 text-red-300 font-medium">
          Field validation: REQUIRED
          <div className="font-normal text-red-400/90 text-xs mt-1">{cell.field_validation_label}</div>
        </div>
      )}
    </div>
  );
}
