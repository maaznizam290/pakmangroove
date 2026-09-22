const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export interface ToolResponse<T = unknown> {
  data: T;
  source: string[];
  timestamp: string;
  parameters: Record<string, unknown>;
  model_version: string | null;
  confidence: number | null;
  limitations: string[];
}

export interface SuitabilityCell {
  cell_id: number;
  lon: number;
  lat: number;
  suitability_score: number;
  confidence: number;
  classification: "VERY_HIGH" | "HIGH" | "MEDIUM" | "LOW" | "EXCLUDED";
  reason_codes: string[];
  data_sources: string[];
  model_version: string;
  local_ecological_risk_evidence: boolean;
  field_validation_label: string;
}

export type Bbox = [number, number, number, number];

function bboxParam(bbox?: Bbox) {
  return bbox ? bbox.join(",") : undefined;
}

async function getJSON<T>(path: string, params: Record<string, string | number | undefined> = {}): Promise<T> {
  const url = new URL(API_BASE + path);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
  });
  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

export interface NamedAoi {
  aoi_id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  bounds: Bbox;
}

export const api = {
  defaultAoi: () => getJSON<{ aoi_id: string; bounds: Bbox }>("/api/v1/aoi/default"),

  listAois: () => getJSON<NamedAoi[]>("/api/v1/aoi/list"),

  restorationSuitability: (bbox?: Bbox, aoi_id?: string) =>
    getJSON<ToolResponse<{ run_id: string | null; cells: SuitabilityCell[] }>>(
      "/api/v1/mangrove/restoration-suitability",
      { bbox: bboxParam(bbox), aoi_id }
    ),

  mangroveMap: (bbox?: Bbox, year?: number) =>
    getJSON<ToolResponse>("/api/v1/mangrove/map", { bbox: bboxParam(bbox), year }),

  extentTimeseries: (bbox?: Bbox) =>
    getJSON<ToolResponse<{ year: number; gain_km2: number; loss_km2: number; net_km2: number; total_extent_km2: number }[]>>(
      "/api/v1/mangrove/extent-timeseries",
      { bbox: bboxParam(bbox) }
    ),

  gmw: (bbox?: Bbox) => getJSON<ToolResponse>("/api/v1/mangrove/gmw", { bbox: bboxParam(bbox) }),

  gbif: (bbox?: Bbox, species?: string) =>
    getJSON<ToolResponse>("/api/v1/mangrove/gbif", { bbox: bboxParam(bbox), species }),

  cgmd: (bbox?: Bbox, year?: number) =>
    getJSON<ToolResponse>("/api/v1/mangrove/cgmd", { bbox: bboxParam(bbox), year }),

  change: (bbox?: Bbox) => getJSON<ToolResponse>("/api/v1/mangrove/change", { bbox: bboxParam(bbox) }),

  healthIndicators: (bbox?: Bbox) => getJSON<ToolResponse>("/api/v1/mangrove/health", { bbox: bboxParam(bbox) }),

  sentinel: (bbox?: Bbox) => getJSON<ToolResponse>("/api/v1/mangrove/sentinel", { bbox: bboxParam(bbox) }),

  forecast: (bbox?: Bbox, horizon_year?: number, model_type?: string) =>
    getJSON<ToolResponse>("/api/v1/mangrove/forecast", { bbox: bboxParam(bbox), horizon_year, model_type }),

  ragSearch: (query: string, top_k = 5) => getJSON<ToolResponse>("/api/v1/rag/search", { query, top_k }),

  ragSources: <T = Record<string, unknown>>() => getJSON<T[]>("/api/v1/rag/sources"),

  models: (task?: string) => getJSON<ToolResponse>("/api/v1/models", { task }),

  reviewQueue: <T = Record<string, unknown>>(status = "pending") => getJSON<T[]>("/api/v1/active-learning/review-queue", { status }),

  hermesAsk: async (question: string, bbox?: Bbox, aoi_id?: string) => {
    const res = await fetch(`${API_BASE}/api/v1/hermes/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, bbox, aoi_id }),
    });
    if (!res.ok) throw new Error(`hermes/ask -> ${res.status}`);
    return res.json();
  },
};
