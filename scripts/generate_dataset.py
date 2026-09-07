"""Synthetic dataset generator.

Produces a reproducible, realistic ticket/event corpus that exercises the full
event vocabulary: status changes, work notes, transfers, approvals, vendor
updates, promised dates, dependencies, assignments, resolutions and reopens -
plus deliberate data-quality edge cases (conflicting statuses, duplicates,
out-of-order events) so the robustness features can be demonstrated.

Outputs:
  data/raw/tickets.csv
  data/raw/events.csv
  data/processed/tickets_processed.csv
  data/processed/events_processed.csv
"""
from __future__ import annotations

import json
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REFERENCE_DATE = date(2026, 9, 7)
SEED = 42
NUM_TICKETS = 100

REGIONS = [
    "North America",
    "Europe",
    "India",
    "Asia Pacific",
    "Middle East",
    "Latin America",
]
SUPPORT_TEAMS = {
    "North America": ["NA Support"],
    "Europe": ["EU Support"],
    "India": ["India Support"],
    "Asia Pacific": ["APAC Support"],
    "Middle East": ["ME Support"],
    "Latin America": ["LATAM Support"],
}
SPECIAL_TEAMS = ["Finance Approval", "Security Review", "Vendor Operations", "Engineering Escalation"]
VENDORS = [
    "Fabricon Global",
    "PartsUnited Express",
    "Northwind Components",
    "Quanta Electronics",
    "Cerule Systems",
    "Oceana Logistics",
]
CATEGORIES = ["Hardware", "Software", "Billing", "Account Management", "Networking", "Application Support"]
PRIORITIES = ["P1", "P2", "P3", "P4"]
APPROVAL_TYPES = ["Finance", "Security", "Procurement", "Legal"]
DELIVERY_ITEMS = ["replacement component", "network switch", "replacement disk", "firmware update", "spare module"]

WORK_NOTES = [
    "Technical investigation completed.",
    "Collected diagnostic logs from the system.",
    "Escalated to the regional product expert for review.",
    "Diagnosis completed; a replacement component is required.",
    "Configuration change scheduled for this week.",
    "Performed first-line troubleshooting; the issue persists.",
    "Root cause identified: outdated firmware.",
    "Replicated the issue in the test environment.",
    "Saved work: waiting for the customer to confirm affected users.",
    "Initial triage completed; created a resolution plan.",
    "Verified the fix in staging; next step is a production change.",
]
VENDOR_UPDATES = [
    "Replacement part is on backorder; delivery is expected to be delayed.",
    "Shipment delayed due to customs clearance; new ETA provided.",
    "Part dispatched; estimated arrival next week.",
    "Component confirmed in stock and will be shipped today.",
    "Vendor reported a manufacturing delay of one week.",
    "Delivery rescheduled due to courier delay.",
    "Component has shipped; tracking received.",
]

SCENARIOS = [
    ("normal_resolve", 26),
    ("approval_resolve", 16),
    ("approval_pending", 11),
    ("vendor_pending", 11),
    ("vendor_resolved", 9),
    ("delayed", 9),
    ("reopened", 7),
    ("multi_transfer", 7),
    ("blocked_dependency", 6),
    ("scheduled_internal", 5),
    ("conflicting", 2),
    ("insufficient", 1),
]


def human_date(d: date) -> str:
    m = ["January", "February", "March", "April", "May", "June",
         "July", "August", "September", "October", "November", "December"][d.month - 1]
    return f"{m} {d.day}"


def make_dt(base: date, offset_hours: int) -> datetime:
    return datetime(base.year, base.month, base.day) + timedelta(hours=offset_hours)


class Generator:
    def __init__(self, seed: int = SEED):
        self.rng = random.Random(seed)
        self.event_counter = 0
        self.tickets: list[dict] = []
        self.events: list[dict] = []

    # ------------------------------------------------------------- helpers
    def new_event_id(self) -> str:
        self.event_counter += 1
        return f"EV-{self.event_counter:05d}"

    def ev(self, ticket_id: str, ts: datetime, etype: str, *, region: str = "", team: str = "",
           old: str | None = None, new: str | None = None, msg: str = "",
           dep_id: str | None = None, dep_title: str | None = None, dep_owner: str | None = None,
           vendor: str | None = None, vendor_item: str | None = None, approval: str | None = None,
           promised: str | None = None, meta: dict | None = None, actor: str = "AGENT",
           event_id: str | None = None) -> dict:
        eid = event_id or self.new_event_id()
        row = {
            "event_id": eid,
            "ticket_id": ticket_id,
            "timestamp": ts.isoformat(),
            "event_type": etype,
            "actor_type": actor,
            "actor_id": "agent-" + self.rng.choice(["a", "b", "c"]) if actor == "AGENT" else actor,
            "region": region,
            "team": team,
            "old_status": old,
            "new_status": new,
            "message": msg,
            "dependency_id": dep_id,
            "dependency_title": dep_title,
            "dependency_owner": dep_owner,
            "vendor": vendor,
            "vendor_item": vendor_item,
            "approval_type": approval,
            "promised_date": promised,
            "metadata": json.dumps({"source": "synthetic", **(meta or {})}),
        }
        self.events.append(row)
        return row

    def status(self, ticket_id: str, ts: datetime, old: str, new: str, region: str, team: str, msg: str = ""):
        return self.ev(ticket_id, ts, "STATUS_CHANGE", region=region, team=team, old=old, new=new, msg=msg)

    def work(self, ticket_id: str, ts: datetime, region: str, team: str, msg: str):
        return self.ev(ticket_id, ts, "WORK_NOTE", region=region, team=team, msg=msg)

    # ------------------------------------------------------------- stories
    def _base(self, idx: int, scenario: str):
        region = self.rng.choice(REGIONS)
        team = self.rng.choice(SUPPORT_TEAMS[region])
        created = REFERENCE_DATE - timedelta(days=self.rng.randint(3, 14))
        tid = f"TCK-{1000 + idx + 1}"
        promised = REFERENCE_DATE + timedelta(days=self.rng.randint(1, 6))
        return {
            "ticket_id": tid,
            "region": region,
            "team": team,
            "created": make_dt(created, self.rng.randint(7, 16)),
            "promised": promised,
            "scenario": scenario,
            "category": self.rng.choice(CATEGORIES),
            "priority": self.rng.choice(PRIORITIES),
            "subject": f"{self.rng.choice(['Replacement', 'Billing', 'Upgrade', 'Outage', 'Configuration'])} request {tid}",
        }

    def _story(self, t: dict):
        tid = t["ticket_id"]
        region, team = t["region"], t["team"]
        created = t["created"]
        promised = t["promised"]
        scenario = t["scenario"]
        vendor = self.rng.choice(VENDORS)
        item = self.rng.choice(DELIVERY_ITEMS)
        approval = self.rng.choice(APPROVAL_TYPES)
        final_status = "OPEN"
        resolution_dt = None
        promised_used = t["promised"]

        def mk(offset_h, etype, **kw):
            return self.ev(tid, created + timedelta(hours=offset_h), etype, region=region, team=team, **kw)

        # Always: created -> assigned (status IN_PROGRESS usually, OPEN for insufficient)
        if scenario == "insufficient":
            final_status = "OPEN"
            return final_status, resolution_dt, None

        s1 = self.status(tid, created, "OPEN", "IN_PROGRESS", region, team, "Assigned for handling.")
        _ = s1
        self.ev(tid, created + timedelta(hours=1), "ASSIGNMENT_CHANGE", region=region, team=team,
                msg=f"Assigned to an agent in {team}.")
        self.ev(tid, created + timedelta(hours=2), "CUSTOMER_UPDATE", region=region, team=team,
                msg="Acknowledgement sent to the customer.")

        if scenario == "normal_resolve":
            t_next = self.rng.randint(3, 9)
            self.work(tid, created + timedelta(hours=t_next), region, team, self.rng.choice(WORK_NOTES))
            promised_dt = created + timedelta(days=self.rng.randint(2, 5))
            promised_used = promised_dt.date()
            self.ev(tid, created + timedelta(hours=t_next + 2), "PROMISED_DATE_SET", region=region, team=team,
                    promised=promised_dt.date().isoformat())
            self.work(tid, created + timedelta(hours=t_next + 4), region, team,
                      "Configuration change scheduled for this week.")
            res = self.rng.choice(["s1", "s2"])
            res_dt = created + timedelta(hours=t_next + 26)
            self.ev(tid, created + timedelta(hours=t_next + 24), "CUSTOMER_UPDATE", region=region, team=team,
                    msg="Progress update sent to the customer.")
            self.ev(tid, res_dt, "RESOLUTION", region=region, team=team, new="RESOLVED",
                    old="IN_PROGRESS", msg="Issue resolved, agreed with the customer.")
            final_status = "RESOLVED"
            resolution_dt = res_dt

        elif scenario == "approval_resolve":
            self.work(tid, created + timedelta(hours=4), region, team, "Technical review completed.")
            self.ev(tid, created + timedelta(hours=6), "APPROVAL_REQUESTED", region=region, team=team,
                    approval=approval, msg=f"{approval} approval requested for the requested change.")
            self.ev(tid, created + timedelta(hours=6), "DEPENDENCY_CREATED", region=region, team=team,
                    dep_id=f"approval:{approval}", dep_title=f"{approval} approval",
                    dep_owner="Finance Approval" if approval == "Finance" else "Security Review")
            self.ev(tid, created + timedelta(hours=6), "PROMISED_DATE_SET", region=region, team=team,
                    promised=promised.isoformat())
            self.ev(tid, created + timedelta(hours=54), "APPROVAL_COMPLETED", region=region, team=team,
                    approval=approval, msg=f"{approval} approval completed.")
            self.ev(tid, created + timedelta(hours=56), "DEPENDENCY_COMPLETED", region=region, team=team,
                    dep_id=f"approval:{approval}")
            res_dt = created + timedelta(hours=58)
            self.ev(tid, created + timedelta(hours=57), "CUSTOMER_UPDATE", region=region, team=team,
                    msg="Progress update sent to the customer.")
            self.ev(tid, res_dt, "RESOLUTION", region=region, team=team, new="RESOLVED",
                    old="IN_PROGRESS", msg="Change implemented and verified.")
            final_status = "RESOLVED"
            resolution_dt = res_dt

        elif scenario == "approval_pending":
            self.work(tid, created + timedelta(hours=4), region, team, "Technical review completed.")
            self.ev(tid, created + timedelta(hours=6), "APPROVAL_REQUESTED", region=region, team=team,
                    approval=approval, msg=f"{approval} approval requested for the requested change.")
            self.ev(tid, created + timedelta(hours=6), "DEPENDENCY_CREATED", region=region, team=team,
                    dep_id=f"approval:{approval}", dep_title=f"{approval} approval",
                    dep_owner="Finance Approval" if approval == "Finance" else "Security Review")
            self.ev(tid, created + timedelta(hours=6), "PROMISED_DATE_SET", region=region, team=team,
                    promised=promised.isoformat())
            self.work(tid, created + timedelta(hours=8), region, team, "Waiting for approval before proceeding.")
            self.ev(tid, created + timedelta(hours=10), "CUSTOMER_UPDATE", region=region, team=team,
                    msg="Progress update sent to the customer.")
            final_status = "PENDING"

        elif scenario in ("vendor_pending", "vendor_resolved"):
            self.work(tid, created + timedelta(hours=4), region, team, "Technical diagnosis completed; a replacement is required.")
            self.ev(tid, created + timedelta(hours=6), "TEAM_TRANSFER", region=region, team="Vendor Operations",
                    msg=f"Transferred to Vendor Operations for {vendor} follow-up.")
            delay = self.rng.randrange(1, 4)
            self.ev(tid, created + timedelta(hours=8), "VENDOR_UPDATE", region=region, team="Vendor Operations",
                    vendor=vendor, vendor_item=item, msg=", ".join([self.rng.choice(VENDOR_UPDATES),
                                                                    f"delivery is expected after {human_date(REFERENCE_DATE + timedelta(days=delay))}"]))
            self.ev(tid, created + timedelta(hours=8), "DEPENDENCY_CREATED", region=region, team="Vendor Operations",
                    dep_id=f"vendor:{vendor}", dep_title=f"Vendor delivery from {vendor}",
                    dep_owner="Vendor Operations", vendor=vendor, vendor_item=item)
            self.ev(tid, created + timedelta(hours=8), "PROMISED_DATE_SET", region=region, team=team,
                    promised=promised.isoformat())
            if scenario == "vendor_resolved":
                self.ev(tid, created + timedelta(hours=60), "VENDOR_UPDATE", region=region, team="Vendor Operations",
                        vendor=vendor, vendor_item=item, msg="Component has shipped; tracking received.")
                self.ev(tid, created + timedelta(hours=61), "DEPENDENCY_COMPLETED", region=region, team="Vendor Operations",
                        dep_id=f"vendor:{vendor}")
                res_dt = created + timedelta(hours=64)
                self.ev(tid, created + timedelta(hours=63), "CUSTOMER_UPDATE", region=region, team=team,
                        msg="Progress update sent to the customer.")
                self.ev(tid, res_dt, "RESOLUTION", region=region, team=team, new="RESOLVED",
                        old="IN_PROGRESS", msg="Replacement installed and verified.")
                final_status = "RESOLVED"
                resolution_dt = res_dt
            else:
                self.ev(tid, created + timedelta(hours=12), "CUSTOMER_UPDATE", region=region, team=team,
                        msg="Progress update sent to the customer.")
                final_status = "PENDING"

        elif scenario == "delayed":
            self.work(tid, created + timedelta(hours=4), region, team, "Initial triage completed; created a resolution plan.")
            promised_past = REFERENCE_DATE - timedelta(days=self.rng.randint(1, 3))
            promised_used = promised_past
            self.ev(tid, created + timedelta(hours=6), "PROMISED_DATE_SET", region=region, team=team,
                    promised=promised_past.isoformat())
            self.work(tid, created + timedelta(hours=50), region, team, "Scheduled replacement part installation.")
            self.ev(tid, created + timedelta(hours=52), "CUSTOMER_UPDATE", region=region, team=team,
                    msg="Progress update sent to the customer.")
            final_status = "PENDING"

        elif scenario == "reopened":
            res_dt = created + timedelta(days=2)
            self.ev(tid, res_dt, "RESOLUTION", region=region, team=team, new="RESOLVED",
                    old="IN_PROGRESS", msg="Issue resolved, agreed with the customer.")
            self.ev(tid, created + timedelta(hours=70), "REOPENED", region=region, team=team,
                    new="REOPENED", msg="Customer reported the issue again; ticket reopened.")
            self.work(tid, created + timedelta(hours=72), region, team, "Reopened; new investigation started.")
            self.ev(tid, created + timedelta(hours=74), "PROMISED_DATE_SET", region=region, team=team,
                    promised=promised.isoformat())
            final_status = "REOPENED"

        elif scenario == "multi_transfer":
            other_regions = [r for r in REGIONS if r != region]
            for i, r2 in enumerate(other_regions[:3]):
                t2 = self.rng.choice(SUPPORT_TEAMS[r2])
                self.ev(tid, created + timedelta(hours=6 + i * 20), "TEAM_TRANSFER", region=r2, team=t2,
                        msg=f"Transferred to {t2} ({r2}).")
                self.work(tid, created + timedelta(hours=8 + i * 20), r2, t2, self.rng.choice(WORK_NOTES))
            self.ev(tid, created + timedelta(hours=70), "PROMISED_DATE_SET", region=region, team=team,
                    promised=promised.isoformat())
            self.work(tid, created + timedelta(hours=72), region, team,
                      "Coordinating handover between the regional teams.")
            final_status = "IN_PROGRESS"

        elif scenario == "blocked_dependency":
            self.work(tid, created + timedelta(hours=4), region, team, "Investigation identified a dependency on engineering.")
            self.ev(tid, created + timedelta(hours=6), "DEPENDENCY_CREATED", region=region, team="Engineering Escalation",
                    dep_id=f"eng-{tid}", dep_title="Engineering escalation",
                    dep_owner="Engineering Escalation", msg="Engineering fix blocked by test environment issue.",
                    meta={"status": "blocked"})
            self.ev(tid, created + timedelta(hours=6), "PROMISED_DATE_SET", region=region, team=team,
                    promised=promised.isoformat())
            self.ev(tid, created + timedelta(hours=30), "VENDOR_UPDATE", region=region, team="Engineering Escalation",
                    vendor=vendor, msg="Engineering fix currently blocked; no ETA.")
            self.work(tid, created + timedelta(hours=40), region, team,
                      "Blocked by the engineering dependency; keeping the customer informed.")
            final_status = "PENDING"

        elif scenario == "scheduled_internal":
            self.work(tid, created + timedelta(hours=4), region, team,
                      "Diagnosis completed; configuration update scheduled.")
            self.ev(tid, created + timedelta(hours=6), "DEPENDENCY_CREATED", region=region, team=team,
                    dep_id="internal:config", dep_title="Configuration update",
                    dep_owner=team, msg="Configuration change scheduled for this week.")
            self.ev(tid, created + timedelta(hours=6), "PROMISED_DATE_SET", region=region, team=team,
                    promised=promised.isoformat())
            self.ev(tid, created + timedelta(hours=8), "CUSTOMER_UPDATE", region=region, team=team,
                    msg="Progress update sent to the customer.")
            final_status = "IN_PROGRESS"

        elif scenario == "conflicting":
            self.work(tid, created + timedelta(hours=4), region, team, "Issue was worked and marked resolved by mistake.")
            self.ev(tid, created + timedelta(hours=6), "STATUS_CHANGE", region=region, team=team,
                    old="IN_PROGRESS", new="RESOLVED", msg="Marked resolved.")
            # conflicting later event: RESOLVED -> IN_PROGRESS
            self.ev(tid, created + timedelta(hours=30), "STATUS_CHANGE", region=region, team=team,
                    old="RESOLVED", new="IN_PROGRESS", msg="Work resumed after review; ticket reopened in the source system.")
            self.ev(tid, created + timedelta(hours=32), "PROMISED_DATE_SET", region=region, team=team,
                    promised=promised.isoformat())
            self.ev(tid, created + timedelta(hours=34), "CUSTOMER_UPDATE", region=region, team=team,
                    msg="Progress update sent to the customer.")
            final_status = "IN_PROGRESS"

        return final_status, resolution_dt, promised_used

    # ------------------------------------------------------------- demo tickets
    def _demo(self):
        self._demo_normal()
        self._demo_approval()
        self._demo_vendor()
        self._demo_overdue()
        self._demo_conflict()
        self._demo_insufficient()
        self._demo_reopened()

    def _demo_normal(self):
        tid = "DEMO-001"
        created = make_dt(REFERENCE_DATE - timedelta(days=4), 9)
        promised = REFERENCE_DATE + timedelta(days=5)
        self.ev(tid, created, "STATUS_CHANGE", region="India", team="India Support",
                old="OPEN", new="IN_PROGRESS", msg="Assigned to India Support.")
        self.ev(tid, created + timedelta(hours=1), "CUSTOMER_UPDATE", region="India", team="India Support",
                msg="Acknowledgement sent to the customer.")
        self.ev(tid, created + timedelta(hours=3), "WORK_NOTE", region="India", team="India Support",
                msg="Technical investigation completed; configuration update identified as the fix.")
        self.ev(tid, created + timedelta(hours=4), "PROMISED_DATE_SET", region="India", team="India Support",
                promised=promised.isoformat())
        self.ev(tid, created + timedelta(hours=5), "WORK_NOTE", region="India", team="India Support",
                msg="Configuration change scheduled for this week.")
        self._add_ticket(tid, "India", "India Support", "IN_PROGRESS", created, promised,
                         "Configuration update required after investigation", "Software", "P2",
                         "Scheduled configuration update", "ACTIVE")

    def _demo_approval(self):
        tid = "DEMO-002"
        created = make_dt(REFERENCE_DATE - timedelta(days=5), 9)
        promised = REFERENCE_DATE + timedelta(days=5)
        self.ev(tid, created, "STATUS_CHANGE", region="Europe", team="EU Support",
                old="OPEN", new="IN_PROGRESS", msg="Assigned to EU Support.")
        self.ev(tid, created + timedelta(hours=1), "CUSTOMER_UPDATE", region="Europe", team="EU Support",
                msg="Acknowledgement sent to the customer.")
        self.ev(tid, created + timedelta(hours=4), "WORK_NOTE", region="Europe", team="EU Support",
                msg="Technical review completed.")
        self.ev(tid, created + timedelta(hours=6), "APPROVAL_REQUESTED", region="Europe", team="EU Support",
                approval="Security", msg="Security approval requested before rollout.")
        self.ev(tid, created + timedelta(hours=6), "DEPENDENCY_CREATED", region="Europe", team="Security Review",
                dep_id="approval:Security", dep_title="Security approval", dep_owner="Security Review")
        self.ev(tid, created + timedelta(hours=6), "PROMISED_DATE_SET", region="Europe", team="EU Support",
                promised=promised.isoformat())
        self.ev(tid, created + timedelta(hours=8), "WORK_NOTE", region="Europe", team="EU Support",
                msg="Waiting for security approval before proceeding.")
        self._add_ticket(tid, "Europe", "EU Support", "PENDING", created, promised,
                         "Security approval required for change", "Application Support", "P2",
                         "Security approval", "ACTIVE")

    def _demo_vendor(self):
        tid = "DEMO-003"
        created = make_dt(REFERENCE_DATE - timedelta(days=6), 9)
        promised = REFERENCE_DATE + timedelta(days=3)
        self.ev(tid, created, "STATUS_CHANGE", region="North America", team="NA Support",
                old="OPEN", new="IN_PROGRESS", msg="Assigned to NA Support.")
        self.ev(tid, created + timedelta(hours=1), "CUSTOMER_UPDATE", region="North America", team="NA Support",
                msg="Acknowledgement sent to the customer.")
        self.ev(tid, created + timedelta(hours=4), "WORK_NOTE", region="North America", team="NA Support",
                msg="Technical diagnosis completed; replacement component required.")
        self.ev(tid, created + timedelta(hours=6), "TEAM_TRANSFER", region="North America", team="Vendor Operations",
                msg="Transferred to Vendor Operations for component follow-up.")
        self.ev(tid, created + timedelta(hours=8), "VENDOR_UPDATE", region="North America", team="Vendor Operations",
                vendor="PartsUnited Express", vendor_item="replacement component",
                msg=f"Replacement component is on backorder; delivery expected after {human_date(REFERENCE_DATE + timedelta(days=2))}. This means the component is delayed.")
        self.ev(tid, created + timedelta(hours=8), "DEPENDENCY_CREATED", region="North America", team="Vendor Operations",
                dep_id="vendor:PartsUnited Express", dep_title="Vendor delivery from PartsUnited Express",
                dep_owner="Vendor Operations", vendor="PartsUnited Express", vendor_item="replacement component")
        self.ev(tid, created + timedelta(hours=9), "PROMISED_DATE_SET", region="North America", team="Vendor Operations",
                promised=promised.isoformat())
        self._add_ticket(tid, "North America", "NA Support", "PENDING", created, promised,
                         "Replacement component required", "Hardware", "P2",
                         "Vendor delivery", "ACTIVE")

    def _demo_overdue(self):
        tid = "DEMO-004"
        created = make_dt(REFERENCE_DATE - timedelta(days=9), 9)
        promised = REFERENCE_DATE - timedelta(days=3)
        self.ev(tid, created, "STATUS_CHANGE", region="Asia Pacific", team="APAC Support",
                old="OPEN", new="IN_PROGRESS", msg="Assigned to APAC Support.")
        self.ev(tid, created + timedelta(hours=1), "CUSTOMER_UPDATE", region="Asia Pacific", team="APAC Support",
                msg="Acknowledgement sent to the customer.")
        self.ev(tid, created + timedelta(hours=6), "WORK_NOTE", region="Asia Pacific", team="APAC Support",
                msg="Initial triage completed; created a resolution plan.")
        self.ev(tid, created + timedelta(hours=8), "PROMISED_DATE_SET", region="Asia Pacific", team="APAC Support",
                promised=promised.isoformat())
        self.ev(tid, created + timedelta(hours=70), "WORK_NOTE", region="Asia Pacific", team="APAC Support",
                msg="Scheduled replacement part installation; waiting for the part.")
        self._add_ticket(tid, "Asia Pacific", "APAC Support", "PENDING", created, promised,
                         "Part installation delayed", "Hardware", "P2",
                         "Part installation", "ACTIVE")

    def _demo_conflict(self):
        tid = "DEMO-005"
        created = make_dt(REFERENCE_DATE - timedelta(days=8), 9)
        promised = REFERENCE_DATE + timedelta(days=2)
        self.ev(tid, created, "STATUS_CHANGE", region="India", team="India Support",
                old="OPEN", new="IN_PROGRESS", msg="Assigned to India Support.")
        self.ev(tid, created + timedelta(hours=1), "CUSTOMER_UPDATE", region="India", team="India Support",
                msg="Acknowledgement sent to the customer.")
        self.ev(tid, created + timedelta(hours=4), "WORK_NOTE", region="India", team="India Support",
                msg="Issue was worked on and marked resolved by mistake.")
        self.ev(tid, created + timedelta(hours=6), "STATUS_CHANGE", region="India", team="India Support",
                old="IN_PROGRESS", new="RESOLVED", msg="Marked resolved.")
        self.ev(tid, created + timedelta(hours=30), "STATUS_CHANGE", region="India", team="India Support",
                old="RESOLVED", new="IN_PROGRESS", msg="Work resumed after review; ticket reopened in source system.")
        self.ev(tid, created + timedelta(hours=32), "PROMISED_DATE_SET", region="India", team="India Support",
                promised=promised.isoformat())
        self._add_ticket(tid, "India", "India Support", "IN_PROGRESS", created, promised,
                         "Conflicting status sequence", "Software", "P3",
                         "Work resumed", "ACTIVE")

    def _demo_insufficient(self):
        tid = "DEMO-006"
        created = make_dt(REFERENCE_DATE - timedelta(days=1), 10)
        self._add_ticket(tid, "North America", "NA Support", "OPEN", created, None,
                         "Insufficient progress information", "Account Management", "P3",
                         "No events recorded", "ACTIVE", has_events=False)

    def _demo_reopened(self):
        tid = "DEMO-007"
        created = make_dt(REFERENCE_DATE - timedelta(days=12), 9)
        promised = REFERENCE_DATE + timedelta(days=4)
        self.ev(tid, created, "STATUS_CHANGE", region="Latin America", team="LATAM Support",
                old="OPEN", new="IN_PROGRESS", msg="Assigned to LATAM Support.")
        self.ev(tid, created + timedelta(hours=1), "CUSTOMER_UPDATE", region="Latin America", team="LATAM Support",
                msg="Acknowledgement sent to the customer.")
        self.work(tid, created + timedelta(hours=3), "Latin America", "LATAM Support",
                  "Investigation completed; fix applied.")
        self.ev(tid, created + timedelta(days=2), "RESOLUTION", region="Latin America", team="LATAM Support",
                old="IN_PROGRESS", new="RESOLVED", msg="Issue resolved, agreed with the customer.")
        self.ev(tid, created + timedelta(days=9), "REOPENED", region="Latin America", team="LATAM Support",
                new="REOPENED", msg="Customer reported the issue again; ticket reopened.")
        self.work(tid, created + timedelta(days=9, hours=3), "Latin America", "LATAM Support",
                  "Reopened; new investigation started.")
        self.ev(tid, created + timedelta(days=9, hours=5), "PROMISED_DATE_SET", region="Latin America", team="LATAM Support",
                promised=promised.isoformat())
        self._add_ticket(tid, "Latin America", "LATAM Support", "REOPENED", created, promised,
                         "Issue recurred after resolution", "Software", "P2",
                         "Reinvestigation", "ACTIVE")

    # ------------------------------------------------------------- edge tickets
    def _edge_cases(self):
        # Out-of-order events: a work note timestamped before ticket creation
        tid = "XTCK-001"
        created = make_dt(REFERENCE_DATE - timedelta(days=4), 9)
        self.ev(tid, created, "STATUS_CHANGE", region="Europe", team="EU Support",
                old="OPEN", new="IN_PROGRESS", msg="Assigned to EU Support.")
        self.ev(tid, created - timedelta(hours=30), "WORK_NOTE", region="Europe", team="EU Support",
                msg="(Out-of-order) Note recorded before the ticket creation timestamp.")
        self.ev(tid, created + timedelta(hours=5), "WORK_NOTE", region="Europe", team="EU Support",
                msg="Investigation in progress.")
        self._add_ticket(tid, "Europe", "EU Support", "IN_PROGRESS", created,
                         REFERENCE_DATE + timedelta(days=4), "Out-of-order event test", "Networking", "P3",
                         "Investigation", "ACTIVE")

        # Duplicate event ids: two events share EV id
        tid = "XTCK-002"
        created = make_dt(REFERENCE_DATE - timedelta(days=3), 10)
        self.ev(tid, created, "STATUS_CHANGE", region="Middle East", team="ME Support",
                old="OPEN", new="IN_PROGRESS", msg="Assigned to ME Support.")
        dupe_id = self.new_event_id()
        self.ev(tid, created + timedelta(hours=3), "WORK_NOTE", region="Middle East", team="ME Support",
                msg="Duplicate event: first instance of this event id.", event_id=dupe_id)
        self.ev(tid, created + timedelta(hours=4), "WORK_NOTE", region="Middle East", team="ME Support",
                msg="Duplicate event: second instance of this event id.", event_id=dupe_id)
        self.ev(tid, created + timedelta(hours=6), "WORK_NOTE", region="Middle East", team="ME Support",
                msg="Investigation ongoing.")
        self._add_ticket(tid, "Middle East", "ME Support", "IN_PROGRESS", created,
                         REFERENCE_DATE + timedelta(days=3), "Duplicate event test", "Application Support", "P4",
                         "Investigation", "ACTIVE")

    # ------------------------------------------------------------- assembly
    def _add_ticket(self, ticket_id: str, region: str, team: str, status: str, created: datetime,
                    promised: date | None, subject: str, category: str, priority: str,
                    ref_suffix: str, sla: str, has_events: bool = True):
        self.tickets.append({
            "ticket_id": ticket_id,
            "customer_reference": f"CUST-{ticket_id[len('DEMO-'):] if ticket_id.startswith('DEMO-') else ticket_id}",  # synthetic only
            "subject": subject,
            "category": category,
            "priority": priority,
            "region": region,
            "current_team": team,
            "current_status": status,
            "created_at": created.isoformat(),
            "updated_at": (created + timedelta(hours=70)).isoformat(),
            "promised_date": promised.isoformat() if promised else None,
            "actual_resolution_date": None,
            "sla_status": sla,
        })

    def run(self) -> None:
        scenario_plan: list[str] = []
        for scenario, count in SCENARIOS:
            scenario_plan.extend([scenario] * count)
        self.rng.shuffle(scenario_plan)

        for idx, scenario in enumerate(scenario_plan):
            t = self._base(idx, scenario)
            final_status, resolution_dt, promised_used = self._story(t)
            tid = t["ticket_id"]
            region, team = t["region"], t["team"]
            sla = "ACTIVE"
            if final_status == "RESOLVED":
                sla = "MET"
                if resolution_dt is not None and promised_used is not None and resolution_dt.date() > promised_used:
                    sla = "BREACHED"
            self._add_ticket(
                tid, region, team, final_status, t["created"],
                promised_used,
                t["subject"], t["category"], t["priority"], "ref", sla.upper(),
            )
            self.tickets[-1]["actual_resolution_date"] = resolution_dt.isoformat() if resolution_dt else None

        self._demo()
        self._edge_cases()

        self._write()

    # ------------------------------------------------------------- output
    def _write(self) -> None:
        raw = ROOT / "data" / "raw"
        processed = ROOT / "data" / "processed"
        raw.mkdir(parents=True, exist_ok=True)
        processed.mkdir(parents=True, exist_ok=True)

        import pandas as pd

        tickets_df = pd.DataFrame(self.tickets)
        events_df = pd.DataFrame(self.events)

        tickets_df.to_csv(raw / "tickets.csv", index=False)
        events_df.to_csv(raw / "events.csv", index=False)

        tickets_df.to_csv(processed / "tickets_processed.csv", index=False)
        events_df.to_csv(processed / "events_processed.csv", index=False)

        manifest = {
            "generated_at": datetime.now().isoformat(),
            "seed": SEED,
            "reference_date": REFERENCE_DATE.isoformat(),
            "tickets": len(self.tickets),
            "events": len(self.events),
            "regions": len(REGIONS),
            "note": "All data is synthetic. No real customer information is used.",
        }
        (processed / "manifest.json").write_text(json.dumps(manifest, indent=2))
        print(f"Dataset written: {len(self.tickets)} tickets, {len(self.events)} events")
        print(f"  -> {raw}")
        print(f"  -> {processed}")


def main() -> None:
    gen = Generator(seed=SEED)
    gen.run()


if __name__ == "__main__":
    main()