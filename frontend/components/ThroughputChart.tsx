"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DashboardStats } from "@/lib/api";

type ThroughputChartProps = {
  stats?: DashboardStats;
};

type ChartPoint = {
  time: number;
  label: string;
  value: number;
};

const MAX_POINTS = 30;

function formatTime(timestamp: number) {
  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(timestamp);
}

export function ThroughputChart({ stats }: ThroughputChartProps) {
  const [points, setPoints] = useState<ChartPoint[]>([]);

  useEffect(() => {
    if (!stats) return;

    const now = Date.now();
    setPoints((current) =>
      [
        ...current,
        {
          time: now,
          label: formatTime(now),
          value: stats.jobs_by_status.SUCCESS,
        },
      ].slice(-MAX_POINTS),
    );
  }, [stats]);

  const throughput = useMemo(() => {
    if (points.length < 2) return 0;
    const latest = points[points.length - 1].value;
    const previous = points[points.length - 2].value;
    return Math.max(0, latest - previous);
  }, [points]);

  return (
    <div className="rounded-lg border border-zinc-900 bg-surface p-4">
      <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-sm font-medium text-white">
            Completed Jobs Over Time
          </h2>
          <p className="text-xs text-zinc-500">
            +{throughput.toLocaleString()} since last poll
          </p>
        </div>
        <p className="text-xs text-zinc-500">
          {points.length.toLocaleString()} samples
        </p>
      </div>

      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={points}
            margin={{ top: 6, right: 12, bottom: 0, left: -20 }}
          >
            <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
            <XAxis
              dataKey="label"
              tick={{ fill: "#71717a", fontSize: 11 }}
              axisLine={{ stroke: "#27272a" }}
              tickLine={false}
              minTickGap={24}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fill: "#71717a", fontSize: 11 }}
              axisLine={{ stroke: "#27272a" }}
              tickLine={false}
            />
            <Tooltip
              cursor={{ stroke: "#71717a" }}
              contentStyle={{
                background: "#0a0a0a",
                border: "1px solid #27272a",
                borderRadius: "8px",
                color: "#ffffff",
              }}
              labelStyle={{ color: "#a1a1aa" }}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#ffffff"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: "#ffffff", stroke: "#ffffff" }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
