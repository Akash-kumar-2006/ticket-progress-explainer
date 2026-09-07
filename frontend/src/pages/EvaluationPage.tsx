import { useCallback, useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api";
import type { EvalRow, EvalSummary } from "../types";
import Badge from "../components/Badge";
import Spinner from "../components/Spinner";
import StatCard from "../components/StatCard";

export default function EvaluationPage() {
  const [summary, setSummary] = useState<EvalSummary | null>(null);
  const [rows, setRows] = useState<EvalRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([api.evalSummary(), api.evalResults()])
      .then(([s, r]) => {
        setSummary(s);
        setRows(r.results);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const run = async () => {
    setRunning(true);
    try {
      await api.runEvaluation();
      await load();
    } finally {
      setRunning(false);
    }
  };

  if (loading) return <Spinner />;

  const chartData = [
    { name: "Understanding", baseline: summary?.baseline_mean_understanding ?? 0, prototype: summary?.prototype_mean_understanding ?? 0 },
    { name: "Follow-up rate %", baseline: (summary?.baseline_followup_rate ?? 0) * 100, prototype: (summary?.prototype_followup_rate ?? 0) * 100 },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Evaluation Dashboard</h1>
          <p className="text-sm text-slate-500">
            Baseline (status-only) vs evidence-grounded prototype across {summary?.num_cases ?? "—"} synthetic cases.
          </p>
        </div>
        <button
          onClick={run}
          disabled={running}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60"
        >
          {running ? "Running…" : "Re-run evaluation"}
        </button>
      </div>

      {!summary?.has_run ? (
        <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
          No evaluation run yet — click "Re-run evaluation".
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatCard label="Understanding" value={(summary?.prototype_mean_understanding ?? 0).toFixed(2)} sub={`baseline ${(summary?.baseline_mean_understanding ?? 0).toFixed(2)}`} accent />
            <StatCard label="Improvement" value={`+${summary.understanding_improvement_pct}%`} sub="prototype vs baseline" />
            <StatCard label="Follow-up rate" value={`${(summary.prototype_followup_rate! * 100).toFixed(0)}%`} sub={`baseline ${(summary.baseline_followup_rate! * 100).toFixed(0)}%`} />
            <StatCard label="Follow-up change" value={`-${summary.followup_reduction_pct}%`} sub="relative reduction" />
            <StatCard label="State accuracy" value={summary.state_accuracy ? `${Math.round(summary.state_accuracy * 100)}%` : "—"} />
            <StatCard label="Blocker accuracy" value={summary.blocker_accuracy ? `${Math.round(summary.blocker_accuracy * 100)}%` : "—"} />
            <StatCard label="Promised date acc." value={summary.promised_date_accuracy ? `${Math.round(summary.promised_date_accuracy * 100)}%` : "—"} />
            <StatCard label="Grounding ≥60" value={summary.grounding_accuracy ? `${Math.round(summary.grounding_accuracy * 100)}%` : "—"} />
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-700">Baseline vs prototype</h2>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="baseline" fill="#94a3b8" />
                <Bar dataKey="prototype" fill="#6366f1" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200 bg-slate-50 uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Case</th>
                  <th className="px-3 py-2">Ticket</th>
                  <th className="px-3 py-2">Expected</th>
                  <th className="px-3 py-2">Prototype</th>
                  <th className="px-3 py-2">Baseline</th>
                  <th className="px-3 py-2">Δ</th>
                  <th className="px-3 py-2">State</th>
                  <th className="px-3 py-2">Blocker</th>
                  <th className="px-3 py-2">Next</th>
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Ground</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.slice(0, 60).map((r) => (
                  <tr key={r.case_id} className="hover:bg-slate-50">
                    <td className="px-3 py-1.5 font-medium">{r.case_id}</td>
                    <td className="px-3 py-1.5">{r.ticket_id}</td>
                    <td className="px-3 py-1.5">
                      <Badge value={r.expected_state} />
                    </td>
                    <td className="px-3 py-1.5 text-slate-600">
                      {r.prototype_understanding}
                      {r.prototype_followup && <span className="ml-1 text-red-500">(follow-up)</span>}
                    </td>
                    <td className="px-3 py-1.5 text-slate-600">{r.baseline_understanding}</td>
                    <td className="px-3 py-1.5">
                      <span className={r.prototype_understanding >= r.baseline_understanding ? "text-emerald-600" : "text-red-500"}>
                        {r.prototype_understanding >= r.baseline_understanding ? "+" : "−"}
                        {Math.abs(r.prototype_understanding - r.baseline_understanding)}
                      </span>
                    </td>
                    <td className="px-3 py-1.5">{r.state_match ? "✓" : "✗"}</td>
                    <td className="px-3 py-1.5">{r.blocker_match ? "✓" : "✗"}</td>
                    <td className="px-3 py-1.5">{r.next_action_match ? "✓" : "✗"}</td>
                    <td className="px-3 py-1.5">{r.date_match ? "✓" : "✗"}</td>
                    <td className="px-3 py-1.5">{r.grounding_ok ? "✓" : "✗"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}