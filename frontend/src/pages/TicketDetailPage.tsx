import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import type {
  AuditRecord,
  DependencyInfo,
  EventRecord,
  ExplanationPayload,
  ExplanationVersion,
  ProgressResult,
  Ticket,
  Timeline,
} from "../types";
import Badge from "../components/Badge";
import Spinner from "../components/Spinner";

function fmtDate(s: string | null | undefined) {
  if (!s) return "—";
  const d = new Date(s);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export default function TicketDetailPage() {
  const { ticketId = "" } = useParams();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [progress, setProgress] = useState<ProgressResult | null>(null);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [deps, setDeps] = useState<DependencyInfo[]>([]);
  const [explanation, setExplanation] = useState<ExplanationPayload | null>(null);
  const [versions, setVersions] = useState<ExplanationVersion[]>([]);
  const [audit, setAudit] = useState<AuditRecord[]>([]);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    Promise.all([
      api.getTicket(ticketId),
      api.progress(ticketId),
      api.timeline(ticketId),
      api.events(ticketId),
      api.dependencies(ticketId),
      api.explanationVersions(ticketId),
      api.audit(ticketId),
    ])
      .then(([t, p, tl, ev, dp, ver, au]) => {
        setTicket(t);
        setProgress(p);
        setTimeline(tl);
        setEvents(ev);
        setDeps(dp);
        setAudit(au.audit);
        setVersions(ver.versions);
      })
      .catch((e) => setError(String(e)));
  }, [ticketId]);

  useEffect(() => {
    load();
  }, [load]);

  const generate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const payload = await api.generateExplanation(ticketId);
      setExplanation(payload);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setGenerating(false);
    }
  };

  if (error && !ticket) return <div className="text-red-600">{error}</div>;
  if (!ticket || !progress) return <Spinner />;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{ticket.ticket_id}</h1>
          <div className="text-sm text-slate-600">{ticket.subject}</div>
          <div className="mt-1 text-xs text-slate-500">
            {ticket.category} · {ticket.region} · opened {fmtDate(ticket.created_at)}
          </div>
        </div>
        <button
          onClick={generate}
          disabled={generating}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60"
        >
          {generating ? "Generating…" : explanation ? "Regenerate explanation" : "Generate explanation"}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-3">
          <div className="text-xs text-slate-500">Progress state</div>
          <div className="mt-1"><Badge value={progress.progress_state} /></div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-3">
          <div className="text-xs text-slate-500">Date status</div>
          <div className="mt-1"><Badge value={progress.date_status} /></div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-3">
          <div className="text-xs text-slate-500">Promised date</div>
          <div className="mt-1 text-sm font-medium">{fmtDate(progress.promised_date)}</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-3">
          <div className="text-xs text-slate-500">Effective status</div>
          <div className="mt-1">
            <Badge value={progress.effective_status} />
          </div>
        </div>
      </div>

      {progress.blockers.length > 0 && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <b>Blockers:</b> {progress.blockers.join(" · ")}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {/* Explanation panel */}
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-700">Generated explanation</h2>
              {explanation && (
                <span className="text-xs text-slate-500">
                  grounding <b>{explanation.grounding_score}</b>/100 · {explanation.model_version} ·
                  rules {explanation.rules_version}
                </span>
              )}
            </div>

            {explanation ? (
              <div className="space-y-4">
                {explanation.insufficient_evidence && (
                  <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
                    Insufficient evidence: the system deliberately reports uncertainty instead of inventing facts.
                  </div>
                )}
                {explanation.conflicts.length > 0 && (
                  <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-xs text-red-800">
                    <b>Data conflict:</b> {explanation.conflicts.join(" · ")}
                  </div>
                )}
                <div className="whitespace-pre-line rounded-lg bg-slate-50 p-4 text-sm leading-relaxed text-slate-800">
                  {explanation.explanation}
                </div>

                <div>
                  <h3 className="mb-2 text-xs font-semibold uppercase text-slate-500">Grounding breakdown</h3>
                  <ul className="space-y-1 text-xs text-slate-600">
                    {explanation.grounding_breakdown.map((line, i) => (
                      <li key={i}>• {line}</li>
                    ))}
                  </ul>
                </div>

                <div>
                  <h3 className="mb-2 text-xs font-semibold uppercase text-slate-500">
                    Claims & supporting evidence
                  </h3>
                  <div className="space-y-2">
                    {explanation.claims.map((c, i) => (
                      <div key={i} className="rounded-lg border border-slate-200 p-3">
                        <div className="flex items-center gap-2">
                          <Badge value={c.category} />
                          <span className={`text-sm ${c.supported ? "text-slate-800" : "text-slate-400 line-through"}`}>
                            {c.text}
                          </span>
                        </div>
                        <div className="mt-1 flex flex-wrap gap-1 text-[11px] text-slate-500">
                          {c.evidence.length ? (
                            c.evidence.map((eid) => <span key={eid} className="rounded bg-indigo-50 px-1.5 py-0.5">{eid}</span>)
                          ) : (
                            <span className="text-red-500">no supporting event</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-500">
                No explanation generated yet. Click the button to generate an evidence-grounded progress explanation for this ticket.
              </p>
            )}
          </div>

          {/* Timeline */}
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-700">Event timeline</h2>
              <span className="text-xs text-slate-500">
                {timeline?.total ?? 0} events
                {timeline && (timeline.duplicates.length || timeline.out_of_order.length || timeline.conflicts.length)
                  ? " · anomalies: " +
                    [timeline.duplicates.length && `${timeline.duplicates.length} dup`, timeline.out_of_order.length && `${timeline.out_of_order.length} out-of-order`, timeline.conflicts.length && `${timeline.conflicts.length} conflict`].filter(Boolean).join(", ")
                  : ""}
              </span>
            </div>
            <ul className="relative space-y-3 border-l border-slate-200 pl-4">
              {timeline?.entries.map((e) => (
                <li key={e.event_id} className="relative">
                  <span className="absolute -left-[21px] top-1 h-2 w-2 rounded-full bg-indigo-400" />
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold text-slate-700">{e.title}</span>
                    <span className="text-[11px] text-slate-400">{fmtDate(e.timestamp)} · {e.team}</span>
                    {e.flags.map((f) => (
                      <span key={f} className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-800">
                        {f}
                      </span>
                    ))}
                  </div>
                  <div className="text-xs text-slate-600">{e.description}</div>
                </li>
              ))}
            </ul>
          </div>

          {/* Dependencies */}
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="mb-3 text-sm font-semibold text-slate-700">Dependency chain</h2>
            {deps.length === 0 ? (
              <p className="text-sm text-slate-500">No dependencies recorded.</p>
            ) : (
              <div className="space-y-2">
                {deps.map((d) => (
                  <div key={d.dependency_id} className="flex items-center gap-3 rounded-lg border border-slate-200 p-3 text-sm">
                    <Badge value={d.kind} />
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-medium">{d.title}</div>
                      <div className="text-xs text-slate-500">
                        {d.owner} · age {d.age_days ?? "—"}d
                        {d.latest_update_message ? ` · ${d.latest_update_message}` : ""}
                      </div>
                    </div>
                    <Badge value={d.status} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="mb-3 text-sm font-semibold text-slate-700">Reasoning</h2>
            <ul className="space-y-1 text-xs text-slate-600">
              {progress.reasons.map((r, i) => (
                <li key={i}>• {r}</li>
              ))}
            </ul>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="mb-3 text-sm font-semibold text-slate-700">Versions & status</h2>
            <ul className="space-y-2 text-xs">
              {versions.map((v) => (
                <li key={v.id} className="flex items-center justify-between rounded-lg border border-slate-200 p-2">
                  <span className="font-medium">v{v.version}</span>
                  <Badge value={v.status} />
                  <span className="text-slate-500">
                    {v.state} · {v.score}
                  </span>
                </li>
              ))}
              {versions.length === 0 && <li className="text-slate-500">No generated versions yet.</li>}
            </ul>
            <div className="mt-3 text-[11px] text-slate-500">Raw events: {events.length}</div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="mb-3 text-sm font-semibold text-slate-700">Audit trail</h2>
            <ul className="space-y-2 text-xs text-slate-600">
              {audit.slice(0, 8).map((a) => (
                <li key={a.audit_id} className="border-b border-slate-100 pb-2 last:border-0">
                  <span className="font-medium text-slate-800">{a.action}</span>
                  <span className="text-slate-400"> · {a.role} · {fmtDate(a.timestamp)}</span>
                  <div className="text-slate-500">
                    {a.old_value && <span>⬆ {a.old_value}</span>}
                    {a.new_value && <span> → {a.new_value}</span>}
                  </div>
                </li>
              ))}
              {audit.length === 0 && <li className="text-slate-500">No audit events.</li>}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}