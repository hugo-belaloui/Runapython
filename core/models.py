"""
Data models for the Runna training plan generator.
All dataclasses used across the application are defined here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# Race distance constants (meters)
# ---------------------------------------------------------------------------
RACE_DISTANCES = {
    "5K": 5000,
    "10K": 10000,
    "HM": 21097.5,
    "Marathon": 42195,
}

# Long run caps per race distance (km)
LONG_RUN_CAPS = {
    "5K": 12.0,
    "10K": 16.0,
    "HM": 24.0,
    "Marathon": 35.0,
}


# ---------------------------------------------------------------------------
# Input dataclass for plan generation
# ---------------------------------------------------------------------------
@dataclass
class PlanInputs:
    """All user-supplied inputs needed to generate a training plan."""

    race_distance: str  # "5K" | "10K" | "HM" | "Marathon"
    race_date: date
    current_weekly_km: float
    recent_race_distance: str  # "5K" | "10K" | "HM" | "Marathon"
    recent_race_time_seconds: int
    days_per_week: int  # 3–7
    long_run_day: int  # 0=Mon … 6=Sun

    @property
    def race_distance_m(self) -> float:
        return RACE_DISTANCES[self.race_distance]

    @property
    def recent_race_distance_m(self) -> float:
        return RACE_DISTANCES[self.recent_race_distance]

    @property
    def recent_race_time_minutes(self) -> float:
        return self.recent_race_time_seconds / 60.0


# ---------------------------------------------------------------------------
# Pace zone
# ---------------------------------------------------------------------------
@dataclass
class PaceZone:
    """A single training pace zone with lower and upper bounds in min/km."""

    zone_name: str
    min_pace_min_km: float  # faster (lower number) end
    max_pace_min_km: float  # slower (higher number) end
    description: str = ""


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
@dataclass
class Session:
    """A single training session on a specific day."""

    date: date
    session_type: str  # "Easy" | "Long Run" | "Tempo" | "Intervals" | "Rest" | "Race"
    distance_km: float
    pace_target_min_km: Optional[float] = None  # target pace in min/km
    notes: str = ""
    status: str = "planned"  # "planned" | "completed" | "skipped"
    id: Optional[int] = None
    plan_id: Optional[int] = None

    @property
    def display_pace(self) -> str:
        """Format pace as M:SS."""
        if self.pace_target_min_km is None:
            return "—"
        mins = int(self.pace_target_min_km)
        secs = int((self.pace_target_min_km - mins) * 60)
        return f"{mins}:{secs:02d}"


# ---------------------------------------------------------------------------
# Week plan
# ---------------------------------------------------------------------------
@dataclass
class WeekPlan:
    """Structure for one training week."""

    week_number: int
    week_start_date: date
    target_weekly_km: float
    phase: str  # "Base" | "Build 1" | "Build 2" | "Taper" | "Race Week"
    sessions: list[Session] = field(default_factory=list)

    @property
    def week_end_date(self) -> date:
        return self.week_start_date + timedelta(days=6)


# ---------------------------------------------------------------------------
# Full plan
# ---------------------------------------------------------------------------
@dataclass
class FullPlan:
    """A complete training plan ready to be saved."""

    name: str
    race_distance: str
    race_date: date
    vdot: float
    current_weekly_km: float
    days_per_week: int
    pace_zones: list[PaceZone]
    weeks: list[WeekPlan]
    id: Optional[int] = None
    
    # Store initial inputs for easy regeneration
    recent_race_distance: str = "5K"
    recent_race_time_seconds: int = 0
    long_run_day: int = 6  # Sunday

    @property
    def total_sessions(self) -> int:
        return sum(len(w.sessions) for w in self.weeks)

    @property
    def total_weeks(self) -> int:
        return len(self.weeks)

    def get_current_week(self) -> Optional[WeekPlan]:
        """Return the week plan that contains today's date."""
        today = date.today()
        for week in self.weeks:
            if week.week_start_date <= today <= week.week_end_date:
                return week
        return None

    def get_current_phase(self) -> str:
        """Return the current phase name."""
        cw = self.get_current_week()
        return cw.phase if cw else "—"

    def get_current_week_number(self) -> int:
        """Return the current week number."""
        cw = self.get_current_week()
        return cw.week_number if cw else 0
        
    def to_inputs(self) -> PlanInputs:
        """Convert plan back to inputs for regeneration."""
        return PlanInputs(
            race_distance=self.race_distance,
            race_date=self.race_date,
            current_weekly_km=self.current_weekly_km,
            recent_race_distance=self.recent_race_distance,
            recent_race_time_seconds=self.recent_race_time_seconds,
            days_per_week=self.days_per_week,
            long_run_day=self.long_run_day,
        )
