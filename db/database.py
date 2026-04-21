"""
SQLite database layer — CRUD operations, schema init, and seed data.

All database interactions go through the Database class.
The DB file is stored as 'runna.db' in the application directory.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from core.models import (
    RACE_DISTANCES,
    FullPlan,
    PaceZone,
    PlanInputs,
    Session,
    WeekPlan,
)
from core.training_engine import generate_full_plan

DB_PATH = Path(__file__).resolve().parent.parent / "runna.db"


class Database:
    """Manages the SQLite database for the Runna app."""

    def __init__(self, db_path: str | Path = DB_PATH):
        self.db_path = str(db_path)
        self.conn: Optional[sqlite3.Connection] = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def connect(self) -> None:
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ------------------------------------------------------------------
    # Schema creation
    # ------------------------------------------------------------------
    def init_schema(self) -> None:
        """Create tables if they don't exist."""
        assert self.conn is not None
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS plans (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT    NOT NULL,
                race_distance   TEXT    NOT NULL,
                race_date       TEXT    NOT NULL,
                vdot            REAL    NOT NULL,
                current_weekly_km REAL  NOT NULL,
                days_per_week   INTEGER NOT NULL,
                created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id         INTEGER NOT NULL,
                date            TEXT    NOT NULL,
                type            TEXT    NOT NULL,
                distance_km     REAL    NOT NULL,
                pace_target_min_km REAL,
                notes           TEXT    DEFAULT '',
                status          TEXT    NOT NULL DEFAULT 'planned',
                phase           TEXT    NOT NULL DEFAULT 'Base',
                FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS pace_zones (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id         INTEGER NOT NULL,
                zone_name       TEXT    NOT NULL,
                min_pace_min_km REAL    NOT NULL,
                max_pace_min_km REAL    NOT NULL,
                description     TEXT    DEFAULT '',
                FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_plan_id ON sessions(plan_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(date);
            CREATE INDEX IF NOT EXISTS idx_pace_zones_plan_id ON pace_zones(plan_id);
        """)
        # Migrate: add phase column if missing (for existing databases)
        self._migrate_add_phase_column()

    def _migrate_add_phase_column(self) -> None:
        """Add 'phase' column to sessions table if it doesn't exist."""
        assert self.conn is not None
        try:
            cols = self.conn.execute("PRAGMA table_info(sessions)").fetchall()
            col_names = [c["name"] for c in cols]
            if "phase" not in col_names:
                self.conn.execute(
                    "ALTER TABLE sessions ADD COLUMN phase TEXT NOT NULL DEFAULT 'Base'"
                )
                self.conn.commit()
            # Migrate: add description to pace_zones if missing
            cols = self.conn.execute("PRAGMA table_info(pace_zones)").fetchall()
            col_names = [c["name"] for c in cols]
            if "description" not in col_names:
                self.conn.execute(
                    "ALTER TABLE pace_zones ADD COLUMN description TEXT DEFAULT ''"
                )
                self.conn.commit()
        except Exception:
            pass  # Ignore migration errors on fresh DBs

    # ------------------------------------------------------------------
    # Plan CRUD
    # ------------------------------------------------------------------
    def save_plan(self, plan: FullPlan) -> int:
        """
        Save a complete plan (plan + all sessions + pace zones)
        in a single transaction. Returns the plan_id.
        """
        assert self.conn is not None
        cur = self.conn.cursor()
        try:
            cur.execute("""
                INSERT INTO plans (name, race_distance, race_date, vdot,
                                   current_weekly_km, days_per_week)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                plan.name,
                plan.race_distance,
                plan.race_date.isoformat(),
                plan.vdot,
                plan.current_weekly_km,
                plan.days_per_week,
            ))
            plan_id = cur.lastrowid

            # Insert pace zones
            for zone in plan.pace_zones:
                cur.execute("""
                    INSERT INTO pace_zones (plan_id, zone_name,
                                            min_pace_min_km, max_pace_min_km,
                                            description)
                    VALUES (?, ?, ?, ?, ?)
                """, (plan_id, zone.zone_name,
                      zone.min_pace_min_km, zone.max_pace_min_km,
                      zone.description))

            # Insert sessions with phase data
            for week in plan.weeks:
                for session in week.sessions:
                    cur.execute("""
                        INSERT INTO sessions (plan_id, date, type, distance_km,
                                              pace_target_min_km, notes, status,
                                              phase)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        plan_id,
                        session.date.isoformat(),
                        session.session_type,
                        session.distance_km,
                        session.pace_target_min_km,
                        session.notes,
                        session.status,
                        week.phase,
                    ))

            self.conn.commit()
            return plan_id
        except Exception:
            self.conn.rollback()
            raise

    def get_all_plans(self) -> list[dict]:
        """Return a list of all plans as dicts (summary info)."""
        assert self.conn is not None
        rows = self.conn.execute(
            "SELECT * FROM plans ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_plan_by_id(self, plan_id: int) -> Optional[FullPlan]:
        """Load a complete FullPlan from the database."""
        assert self.conn is not None

        row = self.conn.execute(
            "SELECT * FROM plans WHERE id = ?", (plan_id,)
        ).fetchone()
        if row is None:
            return None

        plan_data = dict(row)

        # Load pace zones
        zone_rows = self.conn.execute(
            "SELECT * FROM pace_zones WHERE plan_id = ? ORDER BY id",
            (plan_id,)
        ).fetchall()
        pace_zones = []
        for z in zone_rows:
            z_dict = dict(z)
            pace_zones.append(PaceZone(
                zone_name=z_dict["zone_name"],
                min_pace_min_km=z_dict["min_pace_min_km"],
                max_pace_min_km=z_dict["max_pace_min_km"],
                description=z_dict.get("description", ""),
            ))

        # Load sessions with phase data
        session_rows = self.conn.execute(
            "SELECT * FROM sessions WHERE plan_id = ? ORDER BY date, id",
            (plan_id,)
        ).fetchall()

        all_sessions = []
        for s in session_rows:
            s_dict = dict(s)
            all_sessions.append((
                Session(
                    id=s_dict["id"],
                    plan_id=s_dict["plan_id"],
                    date=date.fromisoformat(s_dict["date"]),
                    session_type=s_dict["type"],
                    distance_km=s_dict["distance_km"],
                    pace_target_min_km=s_dict["pace_target_min_km"],
                    notes=s_dict["notes"],
                    status=s_dict["status"],
                ),
                s_dict.get("phase", "Base"),
            ))

        # Group sessions into weeks using stored phase
        weeks: list[WeekPlan] = []
        if all_sessions:
            # Sort by date
            all_sessions.sort(key=lambda x: x[0].date)
            # Group into 7-day weeks starting from first session
            first_date = all_sessions[0][0].date
            # Align to Monday
            week_start = first_date - timedelta(days=first_date.weekday())

            week_num = 1
            current_week_sessions: list[Session] = []
            current_phase = all_sessions[0][1]
            current_start = week_start

            for session, phase in all_sessions:
                while session.date >= current_start + timedelta(days=7):
                    if current_week_sessions:
                        total_km = sum(ss.distance_km for ss in current_week_sessions)
                        weeks.append(WeekPlan(
                            week_number=week_num,
                            week_start_date=current_start,
                            target_weekly_km=round(total_km, 1),
                            phase=current_phase,
                            sessions=current_week_sessions,
                        ))
                    current_week_sessions = []
                    current_start += timedelta(days=7)
                    week_num += 1

                current_week_sessions.append(session)
                current_phase = phase  # Use stored phase

            # Last week
            if current_week_sessions:
                total_km = sum(ss.distance_km for ss in current_week_sessions)
                weeks.append(WeekPlan(
                    week_number=week_num,
                    week_start_date=current_start,
                    target_weekly_km=round(total_km, 1),
                    phase=current_phase,
                    sessions=current_week_sessions,
                ))

        return FullPlan(
            id=plan_data["id"],
            name=plan_data["name"],
            race_distance=plan_data["race_distance"],
            race_date=date.fromisoformat(plan_data["race_date"]),
            vdot=plan_data["vdot"],
            current_weekly_km=plan_data["current_weekly_km"],
            days_per_week=plan_data["days_per_week"],
            pace_zones=pace_zones,
            weeks=weeks,
        )

    def delete_plan(self, plan_id: int) -> None:
        """Delete a plan and cascade to sessions and pace zones."""
        assert self.conn is not None
        self.conn.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
        self.conn.commit()

    def duplicate_plan(self, plan_id: int) -> Optional[int]:
        """Duplicate a plan with all sessions. Returns new plan_id."""
        plan = self.get_plan_by_id(plan_id)
        if plan is None:
            return None
        plan.name = plan.name + " (Copy)"
        plan.id = None
        return self.save_plan(plan)

    # ------------------------------------------------------------------
    # Session CRUD
    # ------------------------------------------------------------------
    def update_session_status(self, session_id: int, status: str) -> None:
        """Update session status (planned/completed/skipped)."""
        assert self.conn is not None
        self.conn.execute(
            "UPDATE sessions SET status = ? WHERE id = ?",
            (status, session_id),
        )
        self.conn.commit()

    def get_sessions_for_date_range(
        self, plan_id: int, start_date: date, end_date: date
    ) -> list[Session]:
        """Get sessions for a plan within a date range."""
        assert self.conn is not None
        rows = self.conn.execute("""
            SELECT * FROM sessions
            WHERE plan_id = ? AND date BETWEEN ? AND ?
            ORDER BY date, id
        """, (plan_id, start_date.isoformat(), end_date.isoformat())).fetchall()

        return [
            Session(
                id=r["id"],
                plan_id=r["plan_id"],
                date=date.fromisoformat(r["date"]),
                session_type=r["type"],
                distance_km=r["distance_km"],
                pace_target_min_km=r["pace_target_min_km"],
                notes=r["notes"],
                status=r["status"],
            )
            for r in rows
        ]

    def get_all_sessions(self, plan_id: int) -> list[Session]:
        """Get all sessions for a plan."""
        assert self.conn is not None
        rows = self.conn.execute("""
            SELECT * FROM sessions WHERE plan_id = ?
            ORDER BY date, id
        """, (plan_id,)).fetchall()

        return [
            Session(
                id=r["id"],
                plan_id=r["plan_id"],
                date=date.fromisoformat(r["date"]),
                session_type=r["type"],
                distance_km=r["distance_km"],
                pace_target_min_km=r["pace_target_min_km"],
                notes=r["notes"],
                status=r["status"],
            )
            for r in rows
        ]

    def get_pace_zones(self, plan_id: int) -> list[PaceZone]:
        """Get pace zones for a plan."""
        assert self.conn is not None
        rows = self.conn.execute(
            "SELECT * FROM pace_zones WHERE plan_id = ? ORDER BY id",
            (plan_id,)
        ).fetchall()
        return [
            PaceZone(
                zone_name=r["zone_name"],
                min_pace_min_km=r["min_pace_min_km"],
                max_pace_min_km=r["max_pace_min_km"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Stats queries
    # ------------------------------------------------------------------
    def get_weekly_stats(self, plan_id: int) -> list[dict]:
        """Aggregate weekly stats for a plan."""
        assert self.conn is not None
        rows = self.conn.execute("""
            SELECT
                strftime('%Y-W%W', date) as week_label,
                MIN(date) as week_start,
                SUM(distance_km) as total_km,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'planned' THEN 1 END) as planned,
                COUNT(CASE WHEN status = 'skipped' THEN 1 END) as skipped,
                COUNT(*) as total_sessions,
                MAX(distance_km) as longest_run,
                AVG(CASE WHEN pace_target_min_km IS NOT NULL
                    THEN pace_target_min_km END) as avg_pace
            FROM sessions
            WHERE plan_id = ? AND type != 'Rest'
            GROUP BY strftime('%Y-W%W', date)
            ORDER BY week_start
        """, (plan_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_session_type_distribution(self, plan_id: int) -> list[dict]:
        """Count sessions by type for a plan."""
        assert self.conn is not None
        rows = self.conn.execute("""
            SELECT type, COUNT(*) as count, SUM(distance_km) as total_km
            FROM sessions
            WHERE plan_id = ? AND type != 'Rest'
            GROUP BY type
            ORDER BY count DESC
        """, (plan_id,)).fetchall()
        return [dict(r) for r in rows]

    def has_plans(self) -> bool:
        """Check if any plans exist in the database."""
        assert self.conn is not None
        count = self.conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
        return count > 0


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------
_db_instance: Optional[Database] = None


def get_database() -> Database:
    """Get or create the global Database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
        _db_instance.connect()
        _db_instance.init_schema()
    return _db_instance
