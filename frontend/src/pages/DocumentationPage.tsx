export default function DocumentationPage() {
  return (
    <div className="max-w-3xl space-y-6 text-sm leading-relaxed text-slate-700">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">How it works</h1>
        <p className="mt-1">
          The generator converts raw ticket events into a short, customer-facing progress
          explanation. Every sentence cites the exact events that support it; where evidence is
          missing the system explicitly says so instead of inventing facts.
        </p>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-semibold text-slate-900">Pipeline</h2>
        <ol className="mt-2 list-inside list-decimal space-y-1">
          <li><b>Timeline engine</b> — sorts events, flags duplicates, out-of-order records and status conflicts.</li>
          <li><b>Dependency engine</b> — builds the chain of approvals, vendor requests, customer waits and internal tasks.</li>
          <li><b>Progress-state engine</b> — rules over effective status + dependencies + dates to pick a transparent state (e.g. WAITING_FOR_VENDOR, BLOCKED, DELAYED).</li>
          <li><b>Date-risk engine</b> — ON_TRACK / AT_RISK / OVERDUE using promised dates and delay evidence.</li>
          <li><b>Evidence selector</b> — picks the relevant events for each claim.</li>
          <li><b>Rule-based generator</b> — composes sentences, each backed by evidence; unsupported claims are dropped or replaced with an uncertainty statement.</li>
          <li><b>Grounding score</b> — a 0-100 transparency score explaining its own calculation.</li>
        </ol>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-semibold text-slate-900">Anti-hallucination guarantees</h2>
        <ul className="mt-2 list-inside list-disc space-y-1">
          <li>Every claim shown must reference at least one real event for the ticket.</li>
          <li>If status/dependency information is insufficient, the output is the generic uncertainty statement — never a fabricated status.</li>
          <li>Conflicts (e.g. RESOLVED then IN_PROGRESS) are surfaced, lowering the grounding score, not silently ignored.</li>
          <li>Promised dates are reported only when a PROMISED_DATE event exists in the evidence.</li>
        </ul>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-semibold text-slate-900">Review & change control</h2>
        <ul className="mt-2 list-inside list-disc space-y-1">
          <li>Generated explanations start as <b>DRAFT</b> and require an approved review before publishing.</li>
          <li>Publication and rollback are restricted by role (REVIEWER/ADMIN) and recorded in the audit trail.</li>
          <li>Every action — generation, approval, publication, rollback — is versioned and auditable per ticket.</li>
        </ul>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-semibold text-slate-900">Demo tickets</h2>
        <p className="mt-1">
          Open <b>DEMO-001 … DEMO-007</b> to see each scenario:
        </p>
        <ul className="mt-2 list-inside list-disc space-y-1">
          <li>DEMO-001 — scheduled work, on track</li>
          <li>DEMO-002 — waiting on an approval</li>
          <li>DEMO-003 — waiting on a vendor, at risk</li>
          <li>DEMO-004 — overdue / delayed</li>
          <li>DEMO-005 — status conflict (resolved then re-opened)</li>
          <li>DEMO-006 — insufficient evidence (safety-net output)</li>
          <li>DEMO-007 — reopened ticket</li>
        </ul>
      </section>
    </div>
  );
}