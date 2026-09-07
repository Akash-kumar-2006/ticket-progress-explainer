import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { Ticket } from "../types";
import Badge from "../components/Badge";
import Spinner from "../components/Spinner";

export default function TicketsPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [stateFilter, setStateFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [limit, setLimit] = useState(25);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string | number> = { limit };
    if (query.trim()) params.search = query.trim();
    if (stateFilter) params.state = stateFilter;
    api
      .listTickets(params)
      .then((r) => {
        setTickets(r.items);
        setTotal(r.total);
      })
      .finally(() => setLoading(false));
  }, [query, stateFilter, limit]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Ticket Explorer</h1>
        <span className="text-sm text-slate-500">{total} tickets</span>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          placeholder="Search ticket id or subject"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          value={stateFilter}
          onChange={(e) => setStateFilter(e.target.value)}
        >
          <option value="">All states</option>
          {[
            "SCHEDULED",
            "IN_PROGRESS",
            "TRANSFERRED",
            "WAITING_FOR_APPROVAL",
            "WAITING_FOR_VENDOR",
            "BLOCKED",
            "DELAYED",
            "INVESTIGATING",
            "REOPENED",
            "RESOLVED",
          ].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
        >
          <option value={25}>25 per page</option>
          <option value={50}>50 per page</option>
          <option value={100}>100 per page</option>
        </select>
        <Link
          to="/tickets/DEMO-001"
          className="ml-auto rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700"
        >
          Open demo ticket
        </Link>
      </div>

      {loading ? (
        <Spinner />
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">Ticket</th>
                <th className="px-4 py-2">Subject</th>
                <th className="px-4 py-2">Team</th>
                <th className="px-4 py-2">Priority</th>
                <th className="px-4 py-2">State</th>
                <th className="px-4 py-2">Date status</th>
                <th className="px-4 py-2">Promised</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {tickets.map((t) => (
                <tr key={t.ticket_id} className="hover:bg-slate-50">
                  <td className="px-4 py-2">
                    <Link to={`/tickets/${t.ticket_id}`} className="font-medium text-indigo-600 hover:underline">
                      {t.ticket_id}
                    </Link>
                  </td>
                  <td className="max-w-[260px] truncate px-4 py-2 text-slate-600">{t.subject}</td>
                  <td className="px-4 py-2 text-slate-600">{t.current_team}</td>
                  <td className="px-4 py-2">
                    <Badge value={t.priority} />
                  </td>
                  <td className="px-4 py-2">
                    <Badge value={t.progress_state ?? t.current_status} />
                  </td>
                  <td className="px-4 py-2">
                    <Badge value={t.date_status} />
                  </td>
                  <td className="px-4 py-2 text-slate-600">{t.promised_date?.slice(0, 10) ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}