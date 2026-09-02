"use client";

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatCurrency } from "@/src/utils/format";

type ChartDataPoint = {
   date: string;
   price: number;
   target: number;
   timestamp: number;
};

type NegotiationChartProps = {
   data: ChartDataPoint[];
};

export function NegotiationChart({ data }: NegotiationChartProps) {
   if (data.length === 0) {
      return (
         <div className="flex h-[200px] items-center justify-center text-sm text-[color:var(--e3-text-soft)]">
            No data available
         </div>
      );
   }

   return (
      <div className="w-full">
         <ResponsiveContainer width="100%" height={200}>
            <LineChart data={data} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
               <XAxis
                  dataKey="date"
                  stroke="#52525b"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
               />
               <YAxis
                  stroke="#52525b"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(value) => `$${(value / 1000).toFixed(1)}k`}
               />
               <Tooltip
                  content={({ active, payload }) => {
                     if (active && payload && payload.length) {
                        // payload[0] = first line (target - dashed blue)
                        // payload[1] = second line (price - solid green)
                        const priceData = payload.find((p) => p.dataKey === "price");
                        const targetData = payload.find((p) => p.dataKey === "target");

                        return (
                           <div className="rounded-lg border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-shell)] p-3 shadow-lg backdrop-blur-xl">
                              <p className="text-xs text-[color:var(--e3-text-soft)] mb-1">
                                 {payload[0].payload.date}
                              </p>
                              <div className="space-y-1">
                                 <p className="text-sm font-semibold text-[color:var(--e3-chip-success-text)]">
                                    Agreed: {formatCurrency((priceData?.value as number) || 0)}
                                 </p>
                                 <p className="text-sm text-[color:var(--e3-text-muted)]">
                                    Target: {formatCurrency((targetData?.value as number) || 0)}
                                 </p>
                              </div>
                           </div>
                        );
                     }
                     return null;
                  }}
               />
               <Line
                  type="monotone"
                  dataKey="target"
                  stroke="#6366f1"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={false}
               />
               <Line
                  type="monotone"
                  dataKey="price"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={{ fill: "#10b981", r: 4 }}
                  activeDot={{ r: 6 }}
               />
            </LineChart>
         </ResponsiveContainer>
         <div className="flex items-center justify-center gap-6 mt-3">
            <div className="flex items-center gap-2">
               <div className="h-0.5 w-8 bg-emerald-500 rounded" />
               <span className="text-xs text-[color:var(--e3-text-muted)]">Agreed Price</span>
            </div>
            <div className="flex items-center gap-2">
               <div className="h-0.5 w-8 border-t-2 border-dashed border-indigo-500 rounded" />
               <span className="text-xs text-[color:var(--e3-text-muted)]">Target Price</span>
            </div>
         </div>
      </div>
   );
}
