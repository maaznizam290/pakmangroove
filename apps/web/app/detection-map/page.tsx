import MapView from "@/components/MapView";

export default function DetectionMapPage() {
  return (
    <div className="flex-1 flex flex-col">
      <div className="p-4 border-b border-neutral-800">
        <h1 className="text-xl font-semibold">Mangrove Detection Map</h1>
        <p className="text-neutral-400 text-sm">Current mangrove probability (RF/GBM baseline) against the GMW v4 reference layer.</p>
      </div>
      <MapView defaultLayer="mangrove_extent" enabledLayers={["mangrove_extent", "gmw_baseline"]} />
    </div>
  );
}
