import axios from "axios";
import type {
  AuditRecord,
  DashboardMetrics,
  DependencyInfo,
  EventRecord,
  EvalRow,
  EvalSummary,
  ExplanationPayload,
  ExplanationVersion,
  ProgressResult,
  Ticket,
  Timeline,
} from "./types";

const http = axios.create({ baseURL: "/api", timeout: 60000 });

export const api = {
  health: () => http.get("/health").then((r) => r.data),

  listTickets: (params: Record<string, string | number> = {}) =>
    http.get("/tickets", { params }).then((r) => r.data),

  getTicket: (id: string) => http.get(`/tickets/${id}`).then((r) => r.data as Ticket),

  events: (id: string) => http.get(`/tickets/${id}/events`).then((r) => r.data as EventRecord[]),

  timeline: (id: string) => http.get(`/tickets/${id}/timeline`).then((r) => r.data as Timeline),

  progress: (id: string) =>
    http.get(`/tickets/${id}/progress`).then((r) => r.data as ProgressResult),

  dependencies: (id: string) =>
    http.get(`/tickets/${id}/dependencies`).then((r) => r.data as DependencyInfo[]),

  generateExplanation: (id: string) =>
    http
      .post(`/tickets/${id}/generate-explanation`, null, {
        headers: { "X-Role": "SYSTEM", "X-Actor": "demo_user" },
      })
      .then((r) => r.data as ExplanationPayload),

  explanationVersions: (id: string) =>
    http.get(`/tickets/${id}/explanation/versions`).then((r) => r.data as { versions: ExplanationVersion[] }),

  audit: (id: string) => http.get(`/tickets/${id}/audit`).then((r) => r.data as { audit: AuditRecord[] }),

  dashboard: () => http.get("/dashboard/metrics").then((r) => r.data as DashboardMetrics),

  evalSummary: () => http.get("/evaluation/summary").then((r) => r.data as EvalSummary),

  evalResults: () => http.get("/evaluation/results").then((r) => r.data as { results: EvalRow[] }),

  runEvaluation: () =>
    http.post("/evaluation/run", null, { headers: { "X-Role": "SYSTEM" } }).then((r) => r.data),
};