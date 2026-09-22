"use client";

import { useState } from "react";
import { api, type Bbox, type NamedAoi, type ToolResponse } from "@/lib/api";
import LimitationsNotice from "@/components/LimitationsNotice";
import AoiSelector from "@/components/AoiSelector";

export default function SatelliteExplorerPage() {
  const [resp, setResp] = useState<ToolResponse | null>(null);
  const [aoi, setAoi] = useState<NamedAoi | null>(null);

  const handleAoiChange = (bounds: Bbox, selected: NamedAoi | null) => {
    setAoi(selected);
    setResp(null);
    api.sentinel(bounds).then(setResp);
  };

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Satellite Explorer</h1>
          <p className="text-neutral-400 text-sm mt-1">
            COPERNICUS/S2_SR_HARMONIZED + COPERNICUS/S2_CLOUD_PROBABILITY — filter, cloud-mask, and composite pipeline
            status for the current AOI.
          </p>
          {aoi && <p className="text-neutral-500 text-xs mt-1">{aoi.name}{aoi.description ? ` — ${aoi.description}` : ""}</p>}
        </div>
        <AoiSelector onChange={handleAoiChange} />
      </div>

      {resp && (
        <>
          <LimitationsNotice limitations={resp.limitations} />
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 text-sm">
            <div className="text-neutral-400 text-xs uppercase tracking-wide mb-2">Sources</div>
            <div>{resp.source.join(", ")}</div>
            <div className="text-neutral-400 text-xs uppercase tracking-wide mt-3 mb-1">Composite status</div>
            <pre className="text-xs text-neutral-300 whitespace-pre-wrap">{JSON.stringify(resp.data, null, 2)}</pre>
          </div>
        </>
      )}
    </div>
  );
}
