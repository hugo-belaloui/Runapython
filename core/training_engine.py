"""
Training math engine — pure Python, zero UI dependencies.

Implements:
  1. Jack Daniels' VDOT calculation
  2. Reverse race-time prediction from VDOT
  3. Five Daniels pace zones derived from VDOT
  4. Pfitzinger-style weekly mileage progression
  5. Session assignment per week
  6. Taper logic
  7. Full plan generation entry point

All formulas sourced from:
  - "Daniels' Running Formula" (Jack Daniels, 3rd ed.)
  - "Advanced Marathoning" (Pete Pfitzinger, 2nd ed.)
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Optional

from core.models import (
    LONG_RUN_CAPS,
    RACE_DISTANCES,
    FullPlan,
    PaceZone,
    PlanInputs,
    Session,
    WeekPlan,
)

# ═══════════════════════════════════════════════════════════════════════════
# 1. VDOT CALCULATION  (Jack Daniels' formula)
# ═══════════════════════════════════════════════════════════════════════════

def _percent_vo2max(time_min: float) -> float:
    """
    Fraction of VO2max sustained for a given race duration.

    Formula (Daniels):
      %VO2max = 0.8 + 0.1894393 * e^(-0.012778 * T)
                    + 0.2989558 * e^(-0.1932605 * T)
    where T = race time in minutes.
    """
    return (
        0.8
        + 0.1894393 * math.exp(-0.012778 * time_min)
        + 0.2989558 * math.exp(-0.1932605 * time_min)
    )


def _vo2_from_velocity(velocity_m_per_min: float) -> float:
    """
    Oxygen cost (ml/kg/min) for a given running velocity.

    Formula (Daniels):
      VO2 = -4.60 + 0.182258 * V + 0.000104 * V^2
    where V = velocity in meters per minute.
    """
    v = velocity_m_per_min
    return -4.60 + 0.182258 * v + 0.000104 * v * v


def calculate_vdot(distance_m: float, time_minutes: float) -> float:
    """
    Compute VDOT fitness index from a race result.

    Steps:
      1. velocity V = distance / time  (m/min)
      2. Compute VO2 at that velocity
      3. Compute %VO2max for that race duration
      4. VDOT = VO2 / %VO2max
    """
    velocity = distance_m / time_minutes  # m/min
    vo2 = _vo2_from_velocity(velocity)
    pct = _percent_vo2max(time_minutes)
    return vo2 / pct


def _time_from_vdot_and_distance(vdot: float, distance_m: float, time_guess: float) -> float:
    """
    Predict race time for a given VDOT and distance using Newton's method.

    We solve:  f(T) = VDOT - VO2(D/T) / %VO2max(T) = 0
    numerically via Newton-Raphson with finite-difference derivative.
    """
    t = time_guess
    max_iter = 200
    for i in range(max_iter):
        v = distance_m / t
        vo2 = _vo2_from_velocity(v)
        pct = _percent_vo2max(t)
        f_val = vdot - vo2 / pct

        # Numerical derivative: df/dt via central difference
        dt = 0.001
        v_plus = distance_m / (t + dt)
        vo2_plus = _vo2_from_velocity(v_plus)
        pct_plus = _percent_vo2max(t + dt)
        f_plus = vdot - vo2_plus / pct_plus

        df = (f_plus - f_val) / dt
        if abs(df) < 1e-15:
            break

        t_new = t - f_val / df
        if t_new < 1.0:
            t_new = 1.0  # clamp to sensible minimum
        
        # Convergence check
        if abs(t_new - t) < 1e-6:
            return t_new
        t = t_new
    
    # Fallback if no convergence: return the last best estimate
    return t


def vdot_to_race_prediction(vdot: float, distance_m: float) -> float:
    """
    Predict race time in minutes for a given VDOT and distance.

    Uses Newton's method starting from a reasonable initial guess
    based on an assumed average pace.
    """
    # Initial guess: assume ~200 m/min pace (5:00/km)
    initial_guess = distance_m / 200.0
    # Safety clamp VDOT to avoid numerical issues
    safe_vdot = max(10.0, min(vdot, 90.0))
    return _time_from_vdot_and_distance(safe_vdot, distance_m, initial_guess)


# ═══════════════════════════════════════════════════════════════════════════
# 2. PACE ZONES FROM VDOT  (Daniels' 5 training zones)
# ═══════════════════════════════════════════════════════════════════════════

def _vdot_velocity(vdot: float) -> float:
    """
    Find the running velocity (m/min) where VO2 equals the given VDOT.

    Solve: VO2(V) = VDOT
      -4.60 + 0.182258*V + 0.000104*V^2 = VDOT
    This is a quadratic in V:
      0.000104*V^2 + 0.182258*V + (-4.60 - VDOT) = 0
    """
    a = 0.000104
    b = 0.182258
    c = -4.60 - vdot
    discriminant = b * b - 4 * a * c
    if discriminant < 0:
        # Fallback: shouldn't happen for reasonable VDOT values
        return 250.0
    # Take the positive root
    v = (-b + math.sqrt(discriminant)) / (2 * a)
    return v


def _velocity_to_pace_min_km(velocity_m_per_min: float) -> float:
    """Convert velocity (m/min) to pace (min/km)."""
    if velocity_m_per_min <= 0:
        return 10.0  # fallback
    return 1000.0 / velocity_m_per_min


def vdot_to_pace_zones(vdot: float) -> dict[str, PaceZone]:
    """
    Derive the 5 Daniels training pace zones from VDOT.

    Zone definitions (fraction of VDOT velocity):
      Easy (E):        59–74%  — aerobic base, recovery
      Marathon (M):    75–84%  — marathon race pace
      Threshold (T):   83–88%  — lactate threshold
      Interval (I):    95–100% — VO2max sessions
      Repetition (R): 105–112% — speed / economy

    Returns dict mapping zone name → PaceZone.
    Pace values are in min/km (lower number = faster pace).
    """
    v_max = _vdot_velocity(vdot)  # m/min at VDOT

    zones_def = [
        ("Easy",        0.59, 0.74, "Aerobic base, recovery"),
        ("Marathon",    0.75, 0.84, "Marathon race pace"),
        ("Threshold",   0.83, 0.88, "Lactate threshold, comfortably hard"),
        ("Interval",    0.95, 1.00, "VO2max sessions"),
        ("Repetition",  1.05, 1.12, "Speed and running economy"),
    ]

    result: dict[str, PaceZone] = {}
    for name, low_frac, high_frac, desc in zones_def:
        # Higher fraction → faster velocity → lower pace number
        fast_pace = _velocity_to_pace_min_km(v_max * high_frac)
        slow_pace = _velocity_to_pace_min_km(v_max * low_frac)
        result[name] = PaceZone(
            zone_name=name,
            min_pace_min_km=fast_pace,  # faster end
            max_pace_min_km=slow_pace,  # slower end
            description=desc,
        )
    return result


def get_zone_midpace(zone: PaceZone) -> float:
    """Return the midpoint pace of a zone in min/km."""
    return (zone.min_pace_min_km + zone.max_pace_min_km) / 2.0


# ═══════════════════════════════════════════════════════════════════════════
# 3. WEEKLY MILEAGE PROGRESSION  (Pfitzinger structure)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_plan_weeks(race_distance: str, race_date: date,
                        current_weekly_km: float) -> int:
    """
    Determine the number of plan weeks (8–24) based on race distance
    and time until race.
    """
    today = date.today()
    days_until = (race_date - today).days
    weeks_available = max(1, days_until // 7)

    # Ideal plan lengths per race distance
    ideal = {"5K": 8, "10K": 10, "HM": 14, "Marathon": 18}
    ideal_weeks = ideal.get(race_distance, 12)

    # Clamp between 8 and 24, and also to what's available
    return max(8, min(24, min(weeks_available, ideal_weeks + 4)))


def _assign_phases(num_weeks: int) -> list[str]:
    """
    Assign training phases to each week index.

    Layout:
      - Last 3 weeks: Taper
      - Last week: Race Week
      - Before taper: split remaining into Base → Build 1 → Build 2
    """
    if num_weeks <= 4:
        # Very short plan: minimal structure
        phases = ["Base"] * max(1, num_weeks - 3)
        phases += ["Taper"] * min(2, num_weeks - 1)
        phases += ["Race Week"]
        return phases[:num_weeks]

    # Reserve last week for race, 3 weeks for taper
    taper_weeks = 3
    race_weeks = 1
    training_weeks = num_weeks - taper_weeks - race_weeks

    # Split training: ~40% Base, ~30% Build 1, ~30% Build 2
    base_weeks = max(2, int(training_weeks * 0.40))
    build1_weeks = max(2, int(training_weeks * 0.30))
    build2_weeks = training_weeks - base_weeks - build1_weeks
    if build2_weeks < 1:
        build2_weeks = 1
        base_weeks = training_weeks - build1_weeks - build2_weeks

    phases: list[str] = []
    phases += ["Base"] * base_weeks
    phases += ["Build 1"] * build1_weeks
    phases += ["Build 2"] * build2_weeks
    phases += ["Taper"] * taper_weeks
    phases += ["Race Week"] * race_weeks

    return phases


def generate_weekly_structure(
    race_distance: str,
    race_date: date,
    current_weekly_km: float,
    days_per_week: int,
) -> list[WeekPlan]:
    """
    Build the weekly km progression backward from race date.

    Rules:
      - Base: +10% per week, capped at max weekly km
      - Every 4th week: recovery (-15%)
      - Build 1 & 2: peak mileage
      - Taper: -20%, -35%, -50% of peak
      - Race Week: minimal volume
    """
    num_weeks = _compute_plan_weeks(race_distance, race_date, current_weekly_km)
    phases = _assign_phases(num_weeks)

    # Compute plan start from race_date
    plan_start = race_date - timedelta(weeks=num_weeks)
    # Align to Monday
    plan_start -= timedelta(days=plan_start.weekday())

    # Peak weekly km target based on race distance
    peak_targets = {
        "5K": min(current_weekly_km * 1.6, 60),
        "10K": min(current_weekly_km * 1.8, 80),
        "HM": min(current_weekly_km * 2.0, 100),
        "Marathon": min(current_weekly_km * 2.2, 130),
    }
    peak_km = peak_targets.get(race_distance, current_weekly_km * 1.5)

    weeks: list[WeekPlan] = []
    prev_km = current_weekly_km
    # Track non-recovery volume separately to avoid sawtooth after recovery
    prev_non_recovery_km = current_weekly_km

    for i, phase in enumerate(phases):
        week_start = plan_start + timedelta(weeks=i)
        week_num = i + 1
        is_recovery = (week_num % 4 == 0)

        if phase == "Base":
            # Progressive build: +10% per week, capped at peak
            target = min(prev_non_recovery_km * 1.10, peak_km)
            # Recovery every 4th week
            if is_recovery:
                target = prev_non_recovery_km * 0.85  # -15% recovery
        elif phase == "Build 1":
            target = min(prev_non_recovery_km * 1.05, peak_km)
            if is_recovery:
                target = prev_non_recovery_km * 0.85
        elif phase == "Build 2":
            target = peak_km
            if is_recovery:
                target = peak_km * 0.85
        elif phase == "Taper":
            # Find how many taper weeks in, count from this point
            taper_idx = sum(1 for p in phases[:i] if p == "Taper")
            reductions = [0.80, 0.65, 0.50]
            reduction = reductions[min(taper_idx, 2)]
            target = peak_km * reduction
        elif phase == "Race Week":
            target = peak_km * 0.30
        else:
            target = prev_non_recovery_km

        # Cap at 10% over previous non-recovery week to avoid spikes
        if phase in ("Base", "Build 1", "Build 2") and not is_recovery:
            target = min(target, prev_non_recovery_km * 1.10)

        target = round(max(target, 10.0), 1)  # minimum 10km/week

        weeks.append(WeekPlan(
            week_number=week_num,
            week_start_date=week_start,
            target_weekly_km=target,
            phase=phase,
        ))
        prev_km = target
        if not is_recovery:
            prev_non_recovery_km = target

    return weeks


# ═══════════════════════════════════════════════════════════════════════════
# 4. SESSION ASSIGNMENT PER WEEK
# ═══════════════════════════════════════════════════════════════════════════

def _distribute_easy_km(total_easy_km: float, num_easy_days: int) -> list[float]:
    """Split easy km roughly evenly across easy days with slight variation."""
    if num_easy_days <= 0:
        return []
    base = total_easy_km / num_easy_days
    result = []
    for i in range(num_easy_days):
        # Alternate slightly shorter/longer for variety
        factor = 0.9 + 0.2 * ((i % 2) * 1.0)
        result.append(round(base * factor, 1))
    # Adjust last day to match total
    diff = total_easy_km - sum(result)
    result[-1] = round(result[-1] + diff, 1)
    return result


def assign_sessions(
    week_plan: WeekPlan,
    vdot: float,
    pace_zones: dict[str, PaceZone],
    long_run_day: int,
    days_available: list[int],
    race_distance: str = "Marathon",
    race_date: Optional[date] = None,
) -> list[Session]:
    """
    Assign training sessions for a single week.

    Phase ratios (of weekly km):
      Base:    ~72% Easy, ~28% Long Run
      Build 1: ~65% Easy, ~25% Long Run, ~10% Tempo
      Build 2: ~58% Easy, ~22% Long Run, ~10% Tempo, ~10% Intervals
      Taper:   ~72% Easy, ~20% Long Run, ~8% Tempo
      Race Week: easy runs + race day
    """
    sessions: list[Session] = []
    weekly_km = week_plan.target_weekly_km
    phase = week_plan.phase
    week_start = week_plan.week_start_date

    # Ensure long_run_day is in available days
    if long_run_day not in days_available:
        days_available = sorted(set(days_available + [long_run_day]))

    # Calculate km per workout type based on phase ratios
    long_run_cap = LONG_RUN_CAPS.get(race_distance, 20.0)
    # Safety: Long run should generally not exceed 35% of weekly volume
    # (except for very low volume plans where it's hard to avoid)
    max_long_proportion = 0.35 if weekly_km > 30 else 0.50

    if phase == "Base":
        long_km = min(weekly_km * 0.28, long_run_cap)
        tempo_km = 0.0
        interval_km = 0.0
    elif phase == "Build 1":
        long_km = min(weekly_km * 0.25, long_run_cap)
        tempo_km = weekly_km * 0.10
        interval_km = 0.0
    elif phase == "Build 2":
        long_km = min(weekly_km * 0.22, long_run_cap)
        tempo_km = weekly_km * 0.10
        interval_km = weekly_km * 0.10
    elif phase == "Taper":
        long_km = min(weekly_km * 0.20, long_run_cap * 0.7)
        tempo_km = weekly_km * 0.08
        interval_km = 0.0
    elif phase == "Race Week":
        long_km = 0.0
        tempo_km = 0.0
        interval_km = 0.0
    else:
        long_km = min(weekly_km * 0.25, long_run_cap)
        tempo_km = 0.0
        interval_km = 0.0

    # Apply safety proportion check
    long_km = min(long_km, weekly_km * max_long_proportion)
    
    # Calculate remaining km for easy runs
    easy_km = weekly_km - long_km - tempo_km - interval_km

    # Clamp all values
    long_km = round(max(long_km, 0), 1)
    tempo_km = round(max(tempo_km, 0), 1)
    interval_km = round(max(interval_km, 0), 1)
    easy_km = round(max(easy_km, 0), 1)

    # Get pace targets
    easy_pace = get_zone_midpace(pace_zones["Easy"])
    long_pace = easy_pace  # Long runs at easy pace
    tempo_pace = get_zone_midpace(pace_zones["Threshold"])
    interval_pace = get_zone_midpace(pace_zones["Interval"])

    # Assign days
    # Priority: long run → tempo → intervals → easy → rest
    assigned_types: dict[int, str] = {}
    assigned_km: dict[int, float] = {}
    assigned_pace: dict[int, float] = {}
    assigned_notes: dict[int, str] = {}

    # Long run
    if long_km > 0:
        assigned_types[long_run_day] = "Long Run"
        assigned_km[long_run_day] = long_km
        assigned_pace[long_run_day] = long_pace
        assigned_notes[long_run_day] = f"Long run at easy pace"

    remaining_days = [d for d in days_available if d != long_run_day]

    # Tempo session (place midweek if possible)
    if tempo_km > 0 and remaining_days:
        # Prefer Wednesday (2) or midweek day
        preferred = [d for d in remaining_days if d in (2, 3)]
        tempo_day = preferred[0] if preferred else remaining_days[0]
        # Tempo workout: warmup + tempo + cooldown
        warmup_cooldown = 3.0  # 1.5km warmup + 1.5km cooldown
        tempo_distance = tempo_km + warmup_cooldown
        # Safety: individual session shouldn't exceed 40% of weekly total
        if tempo_distance > weekly_km * 0.4 and weekly_km > 20:
             tempo_distance = weekly_km * 0.4
             tempo_km = tempo_distance - warmup_cooldown

        assigned_types[tempo_day] = "Tempo"
        assigned_km[tempo_day] = round(tempo_distance, 1)
        assigned_pace[tempo_day] = tempo_pace
        assigned_notes[tempo_day] = (
            f"1.5km warmup, {tempo_km:.1f}km at T-pace "
            f"({_format_pace(tempo_pace)}), 1.5km cooldown"
        )
        remaining_days = [d for d in remaining_days if d != tempo_day]

    # Interval session
    if interval_km > 0 and remaining_days:
        # Prefer Tuesday (1) or another early-week day
        preferred = [d for d in remaining_days if d in (1, 4)]
        interval_day = preferred[0] if preferred else remaining_days[0]
        # Interval workout: warmup + intervals + cooldown
        warmup_cooldown = 3.0
        num_reps = max(3, int(interval_km / 1.0))  # 1km repeats
        rep_distance = 1.0
        total_interval_dist = num_reps * rep_distance + warmup_cooldown
        
        # Safety clamp
        if total_interval_dist > weekly_km * 0.4 and weekly_km > 20:
            total_interval_dist = weekly_km * 0.4
            num_reps = max(1, int((total_interval_dist - warmup_cooldown) / 1.0))

        assigned_types[interval_day] = "Intervals"
        assigned_km[interval_day] = round(total_interval_dist, 1)
        assigned_pace[interval_day] = interval_pace
        assigned_notes[interval_day] = (
            f"1.5km warmup, {num_reps}x1km at I-pace "
            f"({_format_pace(interval_pace)}) with 1km jog recovery, "
            f"1.5km cooldown"
        )
        remaining_days = [d for d in remaining_days if d != interval_day]

    # Easy runs on remaining available days
    # Recalculate easy_km based on what was actually assigned to quality sessions
    quality_km = sum(assigned_km.values())
    easy_km = max(0, weekly_km - quality_km)

    if easy_km > 0 and remaining_days:
        easy_splits = _distribute_easy_km(easy_km, len(remaining_days))
        for day, km in zip(remaining_days, easy_splits):
            assigned_types[day] = "Easy"
            assigned_km[day] = km
            assigned_pace[day] = easy_pace
            assigned_notes[day] = "Easy run"

    # Handle Race Week: add Race Day session
    if phase == "Race Week" and race_date:
        race_weekday = race_date.weekday()
        goal_pace = vdot_to_race_prediction(
            vdot, RACE_DISTANCES.get(race_distance, 42195)
        )
        race_dist_km = RACE_DISTANCES.get(race_distance, 42195) / 1000.0
        goal_pace_min_km = goal_pace / race_dist_km
        assigned_types[race_weekday] = "Race"
        assigned_km[race_weekday] = race_dist_km
        assigned_pace[race_weekday] = goal_pace_min_km
        assigned_notes[race_weekday] = (
            f"RACE DAY — {race_distance} at "
            f"{_format_pace(goal_pace_min_km)} min/km"
        )
        # Remove easy run 1-2 days before race for rest
        for rest_offset in range(1, 3):
            rest_day = (race_weekday - rest_offset) % 7
            if rest_day in assigned_types and assigned_types[rest_day] == "Easy":
                del assigned_types[rest_day]
                del assigned_km[rest_day]
                del assigned_pace[rest_day]
                del assigned_notes[rest_day]

    # Build Session objects for all 7 days
    for day_offset in range(7):
        session_date = week_start + timedelta(days=day_offset)
        weekday = session_date.weekday()

        if weekday in assigned_types:
            sessions.append(Session(
                date=session_date,
                session_type=assigned_types[weekday],
                distance_km=assigned_km[weekday],
                pace_target_min_km=assigned_pace.get(weekday),
                notes=assigned_notes.get(weekday, ""),
                status="planned",
            ))
        else:
            sessions.append(Session(
                date=session_date,
                session_type="Rest",
                distance_km=0.0,
                pace_target_min_km=None,
                notes="Rest or cross-training",
                status="planned",
            ))

    return sessions


def _format_pace(pace_min_km: float) -> str:
    """Format pace as M:SS string."""
    mins = int(pace_min_km)
    secs = int((pace_min_km - mins) * 60)
    return f"{mins}:{secs:02d}"


# ═══════════════════════════════════════════════════════════════════════════
# 5. TAPER LOGIC
# ═══════════════════════════════════════════════════════════════════════════
# Taper logic is integrated into generate_weekly_structure (volume reduction)
# and assign_sessions (session type constraints). The taper phase:
#
#   Week -3: reduce total km by 20%, keep 1 quality session
#   Week -2: reduce by 35%, only easy + 1 short tempo
#   Week -1 (Race Week): reduce by 50-70%, 2-3 short easy runs,
#           rest 2 days before race, race day session
#
# This is handled by the phase-specific logic in both functions above.


# ═══════════════════════════════════════════════════════════════════════════
# 6. FULL PLAN GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def generate_full_plan(inputs: PlanInputs) -> FullPlan:
    """
    Master entry point: generate a complete training plan.

    Pipeline:
      1. Compute VDOT from recent race result
      2. Derive pace zones
      3. Build weekly mileage progression
      4. Assign sessions to each week
      5. Return FullPlan ready for database persistence
    """
    # Step 1: VDOT from recent race
    vdot = calculate_vdot(
        distance_m=inputs.recent_race_distance_m,
        time_minutes=inputs.recent_race_time_minutes,
    )

    # Step 2: Pace zones
    zones = vdot_to_pace_zones(vdot)
    pace_zone_list = list(zones.values())

    # Step 3: Weekly structure
    weeks = generate_weekly_structure(
        race_distance=inputs.race_distance,
        race_date=inputs.race_date,
        current_weekly_km=inputs.current_weekly_km,
        days_per_week=inputs.days_per_week,
    )

    # Step 4: Determine available days from days_per_week
    # Distribute across the week, always including long_run_day
    all_days = list(range(7))
    # Remove some days if days_per_week < 7
    if inputs.days_per_week < 7:
        # Keep long run day, spread the rest
        other_days = [d for d in all_days if d != inputs.long_run_day]
        # Pick evenly-spaced days
        num_other = inputs.days_per_week - 1
        if num_other <= 0:
            available = [inputs.long_run_day]
        else:
            step = max(1, len(other_days) / num_other)
            available = [inputs.long_run_day]
            for i in range(num_other):
                idx = int(i * step) % len(other_days)
                available.append(other_days[idx])
            available = sorted(set(available))
    else:
        available = all_days

    # Step 5: Assign sessions to each week
    for week in weeks:
        week.sessions = assign_sessions(
            week_plan=week,
            vdot=vdot,
            pace_zones=zones,
            long_run_day=inputs.long_run_day,
            days_available=available,
            race_distance=inputs.race_distance,
            race_date=inputs.race_date if week.phase == "Race Week" else None,
        )

    # Build plan name
    plan_name = f"{inputs.race_distance} Plan — {len(weeks)} weeks"

    return FullPlan(
        name=plan_name,
        race_distance=inputs.race_distance,
        race_date=inputs.race_date,
        vdot=round(vdot, 1),
        current_weekly_km=inputs.current_weekly_km,
        days_per_week=inputs.days_per_week,
        pace_zones=pace_zone_list,
        weeks=weeks,
    )
