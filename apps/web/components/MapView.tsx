"use client";

import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { api, type Bbox, type SuitabilityCell } from "@/lib/api";
import CellDetailPanel from "./CellDetailPanel";
import LimitationsNotice from "./LimitationsNotice";

const CLASSIFICATION_COLOR: Record<string, string> = {
  VERY_HIGH: "#10b981",
  HIGH: "#34d399",
  MEDIUM: "#facc15",
  LOW: "#fb923c",
  EXCLUDED: "#525252",
};

type LayerKey = "restoration_suitability" | "mangrove_extent" | "gmw_baseline" | "gbif";

const LAYER_LABELS: Record<LayerKey, string> = {
  restoration_suitability: "Restoration Suitability",
  mangrove_extent: "Mangrove Probability (current)",
  gmw_baseline: "GMW v4 Baseline Extent",
  gbif: "GBIF Observations",
};

// A minimal, self-contained style (no external fetch) rather than a
// hosted basemap URL. MapLibre's own `load` event — which every data
// layer below waits on — only fires once the *style* finishes loading, so
// pointing at an external style.json makes the whole map (including our
// own analytical layers) hostage to that one URL's reachability. This
// repo's dev sandbox blocks the common public demo style's tile domain at
// the network level, and a production/end-user network hiccup on any
// basemap provider would cause the same silent hang. Swap in a real
// vector/raster basemap (MapTiler, Stadia, etc., with an API key) via
// `map.setStyle(...)` after `load` if a prettier background is wanted —
// never as the initial `style`, so our own layers stay independent of it.
const BASEMAP_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": "#0a0a0a" } }],
};

export default function MapView({
  defaultLayer,
  enabledLayers,
}: {
  defaultLayer: LayerKey;
  enabledLayers: LayerKey[];
}) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [bbox, setBbox] = useState<Bbox | null>(null);
  const [visible, setVisible] = useState<Record<LayerKey, boolean>>(() =>
    Object.fromEntries(enabledLayers.map((l) => [l, l === defaultLayer])) as Record<LayerKey, boolean>
  );
  const [selectedCell, setSelectedCell] = useState<SuitabilityCell | null>(null);
  const [limitations, setLimitations] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.defaultAoi().then((aoi) => setBbox(aoi.bounds));
  }, []);

  useEffect(() => {
    if (!mapContainer.current || !bbox || mapRef.current) return;
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: BASEMAP_STYLE,
      bounds: [[bbox[0], bbox[1]], [bbox[2], bbox[3]]],
    });
    map.addControl(new maplibregl.NavigationControl(), "top-left");
    mapRef.current = map;
    return () => {
      // React Strict Mode double-invokes effects in dev (mount -> cleanup
      // -> mount again); without clearing the ref here, the second mount's
      // `mapRef.current` guard above sees a truthy (but removed/destroyed)
      // map and skips creating a real one, leaving every later effect
      // operating on a dead map instance.
      map.remove();
      mapRef.current = null;
    };
  }, [bbox]);

  useEffect(() => {
    if (!mapRef.current || !bbox) return;
    const map = mapRef.current;
    let cancelled = false;

    async function loadLayers() {
      setLoading(true);
      const allLimitations: string[] = [];

      if (visible.restoration_suitability) {
        const resp = await api.restorationSuitability(bbox!);
        allLimitations.push(...resp.limitations);
        const cells = resp.data.cells;
        const geojson: GeoJSON.FeatureCollection = {
          type: "FeatureCollection",
          features: cells
            .filter((c) => c.classification !== "EXCLUDED")
            .map((c) => ({
              type: "Feature",
              geometry: { type: "Point", coordinates: [c.lon, c.lat] },
              properties: c as unknown as GeoJSON.GeoJsonProperties,
            })),
        };
        upsertLayer(map, "restoration_suitability", geojson, "circle", {
          "circle-radius": 5,
          "circle-color": [
            "match", ["get", "classification"],
            "VERY_HIGH", CLASSIFICATION_COLOR.VERY_HIGH,
            "HIGH", CLASSIFICATION_COLOR.HIGH,
            "MEDIUM", CLASSIFICATION_COLOR.MEDIUM,
            "LOW", CLASSIFICATION_COLOR.LOW,
            CLASSIFICATION_COLOR.EXCLUDED,
          ],
          "circle-stroke-width": 1,
          "circle-stroke-color": "#0a0a0a",
        });
      } else {
        removeLayer(map, "restoration_suitability");
      }

      if (visible.gmw_baseline) {
        const resp = await api.gmw(bbox!);
        allLimitations.push(...resp.limitations);
        const rows = resp.data as { geojson: string }[];
        const geojson: GeoJSON.FeatureCollection = {
          type: "FeatureCollection",
          features: rows.map((r) => ({ type: "Feature", geometry: JSON.parse(r.geojson), properties: {} })),
        };
        upsertLayer(map, "gmw_baseline", geojson, "line", { "line-color": "#38bdf8", "line-width": 2 });
      } else {
        removeLayer(map, "gmw_baseline");
      }

      if (visible.gbif) {
        const resp = await api.gbif(bbox!);
        allLimitations.push(...resp.limitations);
        const rows = resp.data as { geojson: string; species: string }[];
        const geojson: GeoJSON.FeatureCollection = {
          type: "FeatureCollection",
          features: rows.map((r) => ({ type: "Feature", geometry: JSON.parse(r.geojson), properties: { species: r.species } })),
        };
        upsertLayer(map, "gbif", geojson, "circle", { "circle-radius": 4, "circle-color": "#a855f7" });
      } else {
        removeLayer(map, "gbif");
      }

      if (visible.mangrove_extent) {
        const resp = await api.mangroveMap(bbox!);
        allLimitations.push(...resp.limitations);
        const rows = (resp.data as { cells: { cell_id: number; probability: number }[] }).cells || [];
        // mangrove_probability_cells has no coordinates of its own in this response — informational only for now
        if (rows.length === 0) allLimitations.push("No mangrove probability cells to render for this AOI yet.");
      }

      if (!cancelled) {
        setLimitations(Array.from(new Set(allLimitations)));
        setLoading(false);
      }
    }

    if (map.isStyleLoaded()) {
      loadLayers().catch((e) => console.error("MapView: failed to load layers", e));
    } else {
      map.once("load", () => {
        loadLayers().catch((e) => console.error("MapView: failed to load layers", e));
      });
    }

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bbox, visible]);

  function upsertLayer(
    map: maplibregl.Map,
    id: LayerKey,
    geojson: GeoJSON.FeatureCollection,
    type: "circle" | "line",
    paint: Record<string, unknown>
  ) {
    const source = map.getSource(id) as maplibregl.GeoJSONSource | undefined;
    if (source) {
      source.setData(geojson);
      return;
    }
    map.addSource(id, { type: "geojson", data: geojson });
    map.addLayer({ id, type, source: id, paint } as maplibregl.LayerSpecification);
    if (id === "restoration_suitability") {
      map.on("click", id, (e) => {
        const feature = e.features?.[0];
        if (feature) setSelectedCell(feature.properties as unknown as SuitabilityCell);
      });
      map.on("mouseenter", id, () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", id, () => (map.getCanvas().style.cursor = ""));
    }
  }

  function removeLayer(map: maplibregl.Map, id: LayerKey) {
    if (map.getLayer(id)) map.removeLayer(id);
    if (map.getSource(id)) map.removeSource(id);
  }

  return (
    <div className="relative flex-1 min-h-[600px]">
      <div ref={mapContainer} className="absolute inset-0" />

      <div className="absolute top-4 left-4 bg-neutral-900/90 border border-neutral-700 rounded-lg p-3 text-sm space-y-1 z-10 w-56">
        <div className="text-neutral-400 text-xs uppercase tracking-wide mb-1">Layers</div>
        {enabledLayers.map((key) => (
          <label key={key} className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={visible[key]}
              onChange={(e) => setVisible((v) => ({ ...v, [key]: e.target.checked }))}
            />
            {LAYER_LABELS[key]}
          </label>
        ))}
        {loading && <div className="text-neutral-500 text-xs pt-1">Loading…</div>}
      </div>

      {selectedCell && <CellDetailPanel cell={selectedCell} onClose={() => setSelectedCell(null)} />}

      <div className="absolute bottom-4 left-4 right-4 z-10">
        <LimitationsNotice limitations={limitations} />
      </div>
    </div>
  );
}
