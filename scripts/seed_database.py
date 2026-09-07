"""Seed the database from the processed synthetic dataset.

Reads data/processed/*_processed.csv and inserts tickets and events, applying
the same normalization/flagging used by live imports. Idempotent.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from backend.app.audit import log_audit
from backend.app.database import SessionLocal, create_all
from backend.app.models.event import Region, Team, TicketEvent, Vendor
from backend.app.models.ticket import Ticket
from backend.app.services.ingestion import normalize_rows_to_orm

PROCESSED = ROOT / "data" / "processed"


def seed() -> dict:
    create_all()
    db = SessionLocal()
    try:
        _seed_ref_tables(db)
        tickets_df = pd.read_csv(PROCESSED / "tickets_processed.csv")
        events_df = pd.read_csv(PROCESSED / "events_processed.csv")

        existing = {r[0] for r in db.query(Ticket.ticket_id).all()}
        tickets_imported = 0
        for _, row in tickets_df.iterrows():
            tid = str(row["ticket_id"])
            if tid in existing:
                continue
            t = Ticket(
                ticket_id=tid,
                customer_reference=str(row.get("customer_reference", "") or f"REF-{tid}"),
                subject=str(row.get("subject", "") or tid),
                category=str(row.get("category", "General")),
                priority=str(row.get("priority", "P3")),
                region=str(row.get("region", "")),
                current_team=str(row.get("current_team", "")),
                current_status=str(row.get("current_status", "OPEN")),
                created_at=_dt(row.get("created_at")),
                updated_at=_dt(row.get("updated_at") or row.get("created_at")),
                promised_date=_dt(row.get("promised_date")),
                actual_resolution_date=_dt(row.get("actual_resolution_date")),
                sla_status=str(row.get("sla_status", "ACTIVE")),
            )
            db.add(t)
            tickets_imported += 1
        db.flush()

        rows = events_df.to_dict(orient="records")
        objects, errors = normalize_rows_to_orm(rows, db)
        for obj in objects:
            db.add(obj)
        duplicate_skips = len(errors)

        log_audit(
            db,
            actor="seed_script",
            role="ADMIN",
            action="TICKET_IMPORTED",
            new_value=f"tickets={tickets_imported}, events={len(objects)}",
            reason=f"seeded from synthetic dataset ({len(errors)} duplicate rows skipped)",
            source="seed",
        )
        db.commit()
        return {
            "tickets_imported": tickets_imported,
            "events_imported": len(objects),
            "duplicate_events_skipped": duplicate_skips,
        }
    finally:
        db.close()


def _seed_ref_tables(db) -> None:
    from backend.app.constants import REGIONS, TEAMS, VENDORS

    if db.query(Region).count() == 0:
        for r in REGIONS:
            db.add(Region(name=r))
    if db.query(Team).count() == 0:
        for t in TEAMS:
            db.add(Team(name=t, region="Global"))
    if db.query(Vendor).count() == 0:
        for v in VENDORS:
            db.add(Vendor(name=v))
    db.commit()


def _dt(value):
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return None
    return pd.Timestamp(value).to_pydatetime()


if __name__ == "__main__":
    print(seed())