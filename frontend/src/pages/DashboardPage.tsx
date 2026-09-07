import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api";
import type { DashboardMetrics } from "../types";
import Badge from "../components/Badge";
import Spinner from "../components/Spinner";
import StatCard from "../components/StatCard";

const PIE_COLORS = [
  "#6366f1",
  "#f59e0b",
  "#10b981",
  "#ef4444",
  "#8b5cf6",
  "#06b6d4",
  "#f97316",
  "#ec4899",
];

export default function DashboardPage() {
  const [data, setData] = useState<DashboardMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.dashboard().then(setData).catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="text-red-600">{error}</div>;
  if (!data) return <Spinner />;

  const stateData = Object.entries(data.states)
    .map(([k, v]) => ({ name: k.replace("state_", ""), value: v }))
    .sort((a, b) => b.value - a.value);
  const regionData = Object.entries(data.regions).map(([name, value]) => ({ name, value }));
  const priorityData = Object.entries(data.priorities).map(([name, value]) => ({ name, value }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Operational Dashboard</h1>
        <div className="text-xs text-slate-500">
          Reference date: <Badge value="2026-09-07" />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Total tickets" value={data.totals.tickets} />
        <StatCard label="Resolved" value={data.totals.resolved ?? 0} />
        <StatCard label="Waiting on approvals" value={data.totals.waiting_approval ?? 0} />
        <StatCard label="Waiting on vendors" value={data.totals.waiting_vendor ?? 0} />
        <StatCard label="Delayed / overdue" value={data.totals.delayed ?? 0} />
        <StatCard label="Blocked" value={data.totals.blocked ?? 0} />
        <StatCard label="In progress" value={data.totals.in_progress ?? 0} />
        <StatCard
          accent
          label="Avg grounding"
          value={data.avg_grounding_score != null ? `${data.avg_grounding_score}/100` : "—"}
          sub="across evaluated tickets"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Progress states</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={stateData}>
              <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-20} height={50} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="value" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="grid grid-cols-1 gap-6">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-700">Tickets by region</h2>
            <ResponsiveContainer width="100%" height={120}>
              <PieChart>
                <Pie data={regionData} dataKey="value" nameKey="name" innerRadius={30} outerRadius={50} paddingAngle={2}>
                  {regionData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-600">
              {regionData.map((r) => (
                <span key={r.name}>
                  {r.name}: <b>{r.value}</b>
                </span>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-700">Priority mix</h2>
            <ResponsiveContainer width="100%" height={120}>
              <PieChart>
                <Pie data={priorityData} dataKey="value" nameKey="name" innerRadius={30} outerRadius={50} paddingAngle={2}>
                  {priorityData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {data.evaluation && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm">
          <b>Latest evaluation:</b> prototype understanding{" "}
          <b>{data.evaluation.prototype_mean_understanding}</b> vs baseline{" "}
          <b>{data.evaluation.baseline_mean_understanding}</b> ({data.evaluation.understanding_improvement_pct}% better)
        </div>
      )}
    </div>
  );
}