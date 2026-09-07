const COLORS: Record<string, string> = {
  RESOLVED: "bg-emerald-100 text-emerald-800",
  COMPLETED: "bg-emerald-100 text-emerald-800",
  WAITING_FOR_APPROVAL: "bg-amber-100 text-amber-800",
  WAITING_FOR_VENDOR: "bg-orange-100 text-orange-800",
  WAITING_FOR_CUSTOMER: "bg-sky-100 text-sky-800",
  WAITING_FOR_INTERNAL_TEAM: "bg-cyan-100 text-cyan-800",
  BLOCKED: "bg-red-100 text-red-800",
  DELAYED: "bg-rose-100 text-rose-800",
  OVERDUE: "bg-rose-100 text-rose-800",
  TRANSFERRED: "bg-violet-100 text-violet-800",
  IN_PROGRESS: "bg-blue-100 text-blue-800",
  INVESTIGATING: "bg-indigo-100 text-indigo-800",
  SCHEDULED: "bg-teal-100 text-teal-800",
  REOPENED: "bg-fuchsia-100 text-fuchsia-800",
  ON_TRACK: "bg-emerald-100 text-emerald-800",
  AT_RISK: "bg-amber-100 text-amber-800",
  ACTIVE: "bg-indigo-100 text-indigo-800",
  MET: "bg-emerald-100 text-emerald-800",
  P1: "bg-red-100 text-red-800",
  P2: "bg-amber-100 text-amber-800",
  P3: "bg-sky-100 text-sky-800",
  P4: "bg-slate-200 text-slate-700",
  NEW: "bg-slate-200 text-slate-700",
  OPEN: "bg-slate-200 text-slate-700",
  PENDING: "bg-slate-200 text-slate-700",
  PENDING_REVIEW: "bg-amber-100 text-amber-800",
  APPROVED: "bg-emerald-100 text-emerald-800",
  PUBLISHED: "bg-emerald-100 text-emerald-800",
  DRAFT: "bg-slate-200 text-slate-700",
  REJECTED: "bg-red-100 text-red-800",
};

export default function Badge({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="text-slate-400 text-xs">—</span>;
  const cls = COLORS[value] ?? "bg-slate-100 text-slate-700";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {value}
    </span>
  );
}