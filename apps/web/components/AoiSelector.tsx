"use client";

import { useEffect, useState } from "react";
import { api, type Bbox, type NamedAoi } from "@/lib/api";

/** Lets a page switch between the seeded named regions (Bundal Island,
 * Sandspit, Keti Bunder / Indus Delta) instead of always querying the
 * default AOI. Falls back to just the default AOI if /aoi/list can't be
 * reached, so pages using this never hard-fail on it. */
export default function AoiSelector({ onChange }: { onChange: (bounds: Bbox, aoi: NamedAoi | null) => void }) {
  const [aois, setAois] = useState<NamedAoi[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");

  useEffect(() => {
    api
      .listAois()
      .then((list) => {
        setAois(list);
        const def = list.find((a) => a.is_default) ?? list[0];
        if (def) {
          setSelectedId(def.aoi_id);
          onChange(def.bounds, def);
        }
      })
      .catch(() => {
        api.defaultAoi().then((aoi) => onChange(aoi.bounds, null));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (aois.length <= 1) return null;

  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-neutral-400">AOI</span>
      <select
        className="bg-neutral-900 border border-neutral-800 rounded-md px-2 py-1 text-neutral-200"
        value={selectedId}
        onChange={(e) => {
          const aoi = aois.find((a) => a.aoi_id === e.target.value);
          if (!aoi) return;
          setSelectedId(aoi.aoi_id);
          onChange(aoi.bounds, aoi);
        }}
      >
        {aois.map((a) => (
          <option key={a.aoi_id} value={a.aoi_id}>
            {a.name}
          </option>
        ))}
      </select>
    </label>
  );
}
