export default function LimitationsNotice({ limitations }: { limitations: string[] }) {
  if (!limitations.length) return null;
  return (
    <div className="bg-amber-950/90 border border-amber-800 rounded-lg p-3 text-amber-300 text-xs space-y-1">
      <div className="uppercase tracking-wide text-amber-500 font-medium">Limitations</div>
      <ul className="list-disc list-inside space-y-0.5">
        {limitations.map((l, i) => (
          <li key={i}>{l}</li>
        ))}
      </ul>
    </div>
  );
}
