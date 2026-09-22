export default function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="bg-red-950/90 border border-red-800 rounded-lg p-3 text-red-300 text-xs space-y-1">
      <div className="uppercase tracking-wide text-red-500 font-medium">Request failed</div>
      <div>{message}</div>
    </div>
  );
}
