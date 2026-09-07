"""Grounding Score.

An interpretable, weighted score between 0 and 100 describing how strongly an
explanation is backed by ticket evidence. This is not a calibrated probability;
it is a transparency aid. The breakdown can be surfaced to the user so the
score is explainable:

  - Evidence coverage: how many of the expected fact categories have evidence
  - Event recency: whether the latest used event is fresh relative to "now"
  - Evidence consistency: whether conflicting events were found
  - Dependency certainty: whether unresolved dependencies have a clear owner/title
  - Date certainty: whether a promised date exists and is parseable
"""
from datetime import timedelta

from ..engines.models import DateAnalysis, DependencyInfo, EvidenceItem, EventData

WEIGHTS = {
    "coverage": 0.40,
    "recency": 0.10,
    "consistency": 0.20,
    "dependency_certainty": 0.15,
    "date_certainty": 0.15,
}


def compute_grounding(
    evidence: list[EvidenceItem],
    events: list[EventData],
    deps: list[DependencyInfo],
    date_info: DateAnalysis,
    now,
    max_recency: timedelta = timedelta(days=30),
) -> tuple[int, list[str]]:
    breakdown: list[str] = []

    # 1. Coverage
    expected_categories = {"status", "work_note", "transfer", "approval", "vendor", "dependency", "date"}
    covered = {cat for it in evidence for cat in _categories_for(it)}
    coverage = len(expected_categories.intersection(covered)) / len(expected_categories)
    breakdown.append(f"Evidence coverage: {len(evidence)} events selected, {len(expected_categories.intersection(covered))} of {len(expected_categories)} fact categories covered")

    # 2. Recency
    latest = max((e.timestamp for e in events), default=None)
    if latest is None:
        recency = 0.0
    elif now - latest <= max_recency:
        recency = 1.0
        breakdown.append("Latest update is recent (within 30 days)")
    else:
        recency = 0.4
        breakdown.append("Latest update is older than 30 days — recency doubtful")

    # 3. Consistency
    conflicts = [e for e in events if e.conflict_flag] or _status_conflicts(events)
    consistency = 0.0 if conflicts else 1.0
    if conflicts:
        breakdown.append(f"Conflicting events detected ({len(conflicts)}) — consistency reduced")
    else:
        breakdown.append("No conflicting events detected")

    # 4. Dependency certainty
    pending = [d for d in deps if d.status in ("pending", "blocked")]
    if not pending:
        dep_cert = 1.0
        breakdown.append("No unresolved dependencies")
    else:
        unknown = [d for d in pending if not d.owner or not d.title or d.owner == "Unknown"]
        dep_cert = 0.8 if not unknown else 0.4
        breakdown.append(
            f"{len(pending)} unresolved dependency detected"
            + (", all with clear owner/title" if not unknown else ", some lack a clear owner")
        )

    # 5. Date certainty
    if date_info.date_status is None:
        date_cert = 0.3
        breakdown.append("No promised date is available — date status uncertain")
    else:
        date_cert = 1.0
        breakdown.append("Promised date available and evaluated")

    score = int(round(
        100.0
        * (
            WEIGHTS["coverage"] * coverage
            + WEIGHTS["recency"] * recency
            + WEIGHTS["consistency"] * consistency
            + WEIGHTS["dependency_certainty"] * dep_cert
            + WEIGHTS["date_certainty"] * date_cert
        )
    ))
    score = max(0, min(100, score))
    breakdown.append(f"Final Grounding Score: {score}/100")
    return score, breakdown


def _categories_for(item: EvidenceItem) -> set[str]:
    mapping = {
        "STATUS_CHANGE": "status",
        "RESOLUTION": "resolution",
        "REOPENED": "reopened",
        "WORK_NOTE": "work_note",
        "TEAM_TRANSFER": "transfer",
        "APPROVAL_REQUESTED": "approval",
        "APPROVAL_COMPLETED": "approval",
        "VENDOR_UPDATE": "vendor",
        "DEPENDENCY_CREATED": "dependency",
        "DEPENDENCY_COMPLETED": "dependency",
        "PROMISED_DATE_SET": "date",
        "PROMISED_DATE_CHANGED": "date",
        "ASSIGNMENT_CHANGE": "assignment",
    }
    return {mapping.get(item.event_type, "other")}


def _status_conflicts(events: list[EventData]) -> list[EventData]:
    status = sorted(
        [e for e in events if e.event_type == "STATUS_CHANGE" and e.new_status],
        key=lambda e: e.timestamp,
    )
    bad: list[EventData] = []
    for prev, cur in zip(status, status[1:]):
        if prev.new_status == "RESOLVED" and cur.new_status in ("OPEN", "IN_PROGRESS", "PENDING", "ESCALATED", "REOPENED"):
            bad.append(cur)
    return bad