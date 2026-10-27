"use client"

import { Line, LineChart, ResponsiveContainer, YAxis } from "recharts"

export function Sparkline({ 
  data, 
  dataKey = "value", 
  color = "var(--accent)",
  height = 60
}: { 
  data: any[];
  dataKey?: string;
  color?: string;
  height?: number;
}) {
  if (!data || data.length === 0) return null;
  return (
    <div style={{ height: `${height}px` }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <YAxis domain={['dataMin', 'dataMax']} hide />
          <Line
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            strokeWidth={2}
            dot={false}
            isAnimationActive={true}
            animationDuration={1500}
            animationEasing="ease-out"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
