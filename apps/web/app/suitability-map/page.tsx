import MapView from "@/components/MapView";

export default function SuitabilityMapPage() {
  return (
    <div className="flex-1 flex flex-col">
      <div className="p-4 border-b border-neutral-800">
        <h1 className="text-xl font-semibold">Restoration Suitability Map</h1>
        <p className="text-neutral-400 text-sm">
          Click any colored cell for its score, confidence, reason codes, and data sources. Every HIGH/VERY_HIGH
          result is a candidate only — field validation required, never a planting instruction.
        </p>
      </div>
      <MapView defaultLayer="restoration_suitability" enabledLayers={["restoration_suitability", "gmw_baseline", "gbif"]} />
    </div>
  );
}
