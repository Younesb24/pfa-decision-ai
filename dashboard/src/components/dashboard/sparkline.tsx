"use client";

import { Area, AreaChart, ResponsiveContainer, YAxis } from "recharts";

interface SparklineProps {
  data: number[];
  /** Hex color for stroke + gradient fill */
  color: string;
  /** Pixel height; default 36 */
  height?: number;
  /** Show area fill gradient; default true */
  fill?: boolean;
}

/**
 * Micro chart embedded in KPI tiles. No axes, no grid, no tooltip —
 * just the silhouette of the trend with a soft gradient fill.
 */
export function Sparkline({
  data,
  color,
  height = 36,
  fill = true,
}: SparklineProps) {
  if (!data || data.length === 0) {
    return <div style={{ height }} className="w-full" />;
  }

  const seriesId = `spark-${color.replace(/[^a-zA-Z0-9]/g, "")}`;
  const chartData = data.map((v, i) => ({ i, v }));

  return (
    <div style={{ height }} className="w-full -mx-1">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={chartData}
          margin={{ top: 2, right: 2, bottom: 2, left: 2 }}
        >
          <defs>
            <linearGradient id={seriesId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.35} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <YAxis hide domain={["dataMin - 1", "dataMax + 1"]} />
          <Area
            type="monotone"
            dataKey="v"
            stroke={color}
            strokeWidth={1.6}
            fill={fill ? `url(#${seriesId})` : "none"}
            isAnimationActive={false}
            dot={false}
            activeDot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
