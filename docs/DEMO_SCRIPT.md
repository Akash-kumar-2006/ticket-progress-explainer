# Evaluation demo script (30–45 min)

Goal: prove the three thesis claims with a laptop, no internet, no credentials:

1. **The explanation is evidence-grounded** — every sentence has a supporting event.
2. **It beats the status-only baseline** — measured, not asserted.
3. **Bad data is handled honestly** — conflicts/insufficiency surface instead of hallucination.

---

## Part 0 — Setup check (5 min)

```bash
cd "D:\ticket project"

# 1. Backend up
cd backend
uvicorn app.main:app --port 8000        # keep running
```
Confirm: `http://127.0.0.1:8000/api/health` →
`{"status":"ok","rules_version":"1.0.0",...}`

Optional dev UI: `cd frontend && npm run dev` (or use the single-server build —
the SPA is already served at `http://127.0.0.1:8000/`).

## Part 1 — The dataset is real and validated (5 min)

```bash
python -m scripts.validate_dataset
cat data/processed/validation_report.json
```
Point out: 119 tickets, 1022 events, **0 ticket issues**, and the 4 *deliberate*
event issues (3 conflicts + 1 out-of-order) — the dataset is reproducible (seed 42).

## Part 2 — Live generation & the evidence rule (10 min)

Open `http://127.0.0.1:8000/tickets/TCK-1001` (via the SPA or API):

```bash
curl -X POST http://127.0.0.1:8000/api/tickets/TCK-1001/generate-explanation
```

Walk through the JSON:
- `progress_state=WAITING_FOR_VENDOR`, `date_status=ON_TRACK`
- the rendered explanation paragraphs
- `claims`: every entry has `evidence: [...]` and `supported: true`
- `grounding_breakdown`: show the weights (coverage/recency/consistency/dependency/date)

Then **tour the 7 demo scenarios** in the Ticket Explorer:

| Ticket | Expect | Point out |
|--------|--------|-----------|
| DEMO-001 | SCHEDULED, ON_TRACK | next action from a work note |
| DEMO-002 | WAITING_FOR_APPROVAL | approval dependency visible |
| DEMO-003 | WAITING_FOR_VENDOR, AT_RISK | "may not be met" wording is honest |
| DEMO-004 | DELAYED, OVERDUE | promised date passed + unresolved |
| DEMO-005 | IN_PROGRESS + **conflict banner** | RESOLVED→IN_PROGRESS surfaced, grounding 57 |
| DEMO-006 | **insufficient-evidence safety net** | generic uncertainty, no invented status |
| DEMO-007 | REOPENED | reopen explanation |

## Part 3 — Anti-hallucination demo (5 min)

- Show DEMO-006: the output says *"the available updates do not provide enough
  information…"* — it does not invent "resolved" or a fake reason.
- Show DEMO-005: the system *remembers* the contradiction (conflict banner,
  lower grounding) instead of hiding it.
- State the guarantee: *every emitted claim must reference at least one real
  event; tests enforce it.*

## Part 4 — Review → publish → rollback + audit (5 min)

Via API (or the UI):
1. Generate → DRAFT.
2. Approve as REVIEWER (×2 → APPROVED), then publish.
3. Try to publish as SUPPORT_AGENT → **403**.
4. Rollback as ADMIN → new version created; audit trail shows every action.

Show `GET /api/tickets/TCK-1001/audit`: EXPLANATION_GENERATED → APPROVED →
PUBLISHED → ROLLBACK_EXECUTED, each with actor/role/old→new.

## Part 5 — The experiment (10 min)

```bash
python -m scripts.run_evaluation
```

Show `data/evaluation/evaluation_cases.csv` has `baseline_score`/`prototype_score`
filled. Open the **Evaluation** page in the UI:

- Understanding: baseline 2.34 → prototype 4.36 (**+86%**)
- Follow-up needed: 57.8% → 26.6% (**−54%**)
- State 76.6% · Blocker 79.2% · Next-action 48.6% · Date 96.9% · Grounding 85.9%

Blocker/date/grounding are the *core* win; next-action is honestly lower.

## Part 6 — Tests & wrap-up (5 min)

```bash
python -m pytest     # 47 passed
```

Close with the honest-limitations slide (docs/LIMITATIONS.md): synthetic data,
snapshot date, no LLM by default, next-action ≈ 49%.

---

## Anti-goals (what to *avoid* showing)

- Do not claim the reviewer is human (the reviewer is a documented rule).
- Do not claim production-readiness for the role headers (demo-only).
- Do not hide next-action accuracy or the synthetic-data boundary.