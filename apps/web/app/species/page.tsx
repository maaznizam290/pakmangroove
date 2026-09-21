"use client";

import { useEffect, useState } from "react";
import { api, type ToolResponse } from "@/lib/api";
import LimitationsNotice from "@/components/LimitationsNotice";

interface GbifRow {
  occurrence_id: string;
  species: string;
  event_date: string | null;
  basis_of_record: string | null;
}

export default function SpeciesExplorerPage() {
  const [resp, setResp] = useState<ToolResponse<GbifRow[]> | null>(null);

  useEffect(() => {
    api.defaultAoi().then((aoi) => api.gbif(aoi.bounds)).then(setResp as never);
  }, []);

  const rows = resp?.data || [];

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Species Explorer</h1>
        <p className="text-neutral-400 text-sm mt-1">
          GBIF occurrence records for the current AOI. GBIF and peer-reviewed literature take precedence over any
          secondary Kaggle species dataset in case of conflict.
        </p>
      </div>

      {resp && <LimitationsNotice limitations={resp.limitations} />}

      {rows.length > 0 ? (
        <ul className="space-y-2">
          {rows.map((r) => (
            <li key={r.occurrence_id} className="bg-neutral-900 border border-neutral-800 rounded p-3 text-sm">
              <div className="font-medium italic">{r.species}</div>
              <div className="text-neutral-400 text-xs">{r.event_date ?? "date unknown"} · {r.basis_of_record ?? "basis unknown"}</div>
            </li>
          ))}
        </ul>
      ) : (
        resp && <div className="text-neutral-500 text-sm">No GBIF records ingested for this AOI yet.</div>
      )}
    </div>
  );
}
