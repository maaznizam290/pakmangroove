"use client";

import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { api } from "@/lib/api";
import LimitationsNotice from "@/components/LimitationsNotice";

interface YearRow {
  year: number;
  gain_km2: number;
  loss_km2: number;
  net_km2: number;
  total_extent_km2: number;
}

export default function TimelinePage() {
  const [rows, setRows] = useState<YearRow[]>([]);
  const [limitations, setLimitations] = useState<string[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api.defaultAoi()
      .then((aoi) => api.extentTimeseries(aoi.bounds))
      .then((resp) => {
        setRows(resp.data || []);
        setLimitations(resp.limitations);
        setLoaded(true);
      });
  }, []);

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Historical Timeline</h1>
        <p className="text-neutral-400 text-sm mt-1">Annual mangrove extent, gain, and loss (CGMD-Extent30, 1984–2023). OBSERVED / DERIVED, never a forecast.</p>
      </div>

      <LimitationsNotice limitations={limitations} />

      {rows.length > 0 ? (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4" style={{ height: 400 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
              <XAxis dataKey="year" stroke="#a3a3a3" />
              <YAxis stroke="#a3a3a3" label={{ value: "km²", angle: -90, position: "insideLeft", fill: "#a3a3a3" }} />
              <Tooltip contentStyle={{ background: "#171717", border: "1px solid #404040" }} />
              <Legend />
              <Line type="monotone" dataKey="total_extent_km2" name="Total extent" stroke="#10b981" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="gain_km2" name="Gain" stroke="#38bdf8" dot={false} />
              <Line type="monotone" dataKey="loss_km2" name="Loss" stroke="#f87171" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        loaded && <div className="text-neutral-500">No extent time series ingested for the default AOI yet.</div>
      )}
    </div>
  );
}
