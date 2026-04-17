import datetime
import math
from typing import List, Dict, Tuple
from core.vdot_calc import get_paces_from_vdot

def generate_plan(
    user_id: int,
    start_date_str: str,
    race_date_str: str,
    goal_distance_km: float,
    vdot: float,
    available_days: List[int]
) -> Dict:
    """
    Generates a full training plan based on weeks to race, VDOT, and available days.
    """
    start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
    race_date = datetime.datetime.strptime(race_date_str, "%Y-%m-%d").date()

    days_to_race = (race_date - start_date).days

    if days_to_race <= 0:
        return {"error": "Race date is too close."}

    # Use ceil to include partial final week (so race day isn't dropped)
    total_weeks = math.ceil(days_to_race / 7)

    if total_weeks <= 0:
        return {"error": "Race date is too close."}

    paces = get_paces_from_vdot(vdot)

    # Determine Plan Type
    if total_weeks < 8:
        plan_type = "Tapering/Crash"
        weeks_to_generate = total_weeks
        base_weeks = 0
        specific_weeks = max(0, total_weeks - 2)
        taper_weeks = min(2, total_weeks)
    elif total_weeks <= 16:
        plan_type = "Specific"
        weeks_to_generate = total_weeks
        base_weeks = 0
        specific_weeks = max(0, total_weeks - 3)
        taper_weeks = min(3, total_weeks)
    else:
        plan_type = "Base Building + Specific"
        weeks_to_generate = total_weeks
        base_weeks = total_weeks - 16
        specific_weeks = 13
        taper_weeks = 3

    workouts = []

    if not available_days:
        available_days = [1, 3, 5, 6] # Default to Mon, Wed, Fri, Sat

    # Simple logic for assigning days
    # Usually: Long run on the weekend (Day 6 or 0)
    # Easy run, Quality run, Easy run.
    sorted_days = sorted(available_days)
    long_run_day = sorted_days[-1]
    quality_run_day = sorted_days[len(sorted_days)//2] if len(sorted_days) > 1 else sorted_days[0]
    easy_run_days = [d for d in sorted_days if d not in (long_run_day, quality_run_day)]

    # Mileage scaling based on distance and phase
    max_long_run_km = goal_distance_km * 0.85 # up to 85% of race distance
    if goal_distance_km >= 42.195:
        max_long_run_km = 32.0 # Cap marathon long runs

    current_date = start_date

    for week in range(1, total_weeks + 1):
        # Determine week phase
        if week <= base_weeks:
            phase = "Base"
            intensity_factor = 0.5 + (0.3 * (week / base_weeks)) if base_weeks > 0 else 0.8
        elif week <= base_weeks + specific_weeks:
            phase = "Specific"
            progress = (week - base_weeks) / specific_weeks if specific_weeks > 0 else 1.0
            intensity_factor = 0.8 + (0.2 * progress)
        else:
            phase = "Taper"
            taper_progress = (week - (base_weeks + specific_weeks)) / taper_weeks if taper_weeks > 0 else 1.0
            intensity_factor = 1.0 - (0.4 * taper_progress) # Reduce volume by up to 40%

        week_long_run_km = max(5.0, max_long_run_km * intensity_factor)
        week_easy_run_km = max(3.0, week_long_run_km * 0.4)
        week_quality_km = max(4.0, week_long_run_km * 0.5)

        for day_idx in range(7):
            day_date = current_date + datetime.timedelta(days=(week-1)*7 + day_idx)

            # Don't generate workouts past race day
            if day_date > race_date:
                continue

            day_of_week = day_date.weekday() # 0 = Monday, 6 = Sunday

            if day_of_week not in sorted_days:
                continue

            workout_type = ""
            title = ""
            desc = ""
            target_distance = 0.0
            target_pace = 0

            if day_of_week == long_run_day:
                workout_type = "Long Run"
                title = f"Long Run ({phase})"
                target_distance = round(week_long_run_km, 1)
                target_pace = paces.get('E', 360) # E pace
                desc = f"Easy long run. Maintain a conversational pace."
            elif day_of_week == quality_run_day:
                if phase == "Base":
                    workout_type = "Easy"
                    title = "Aerobic Base"
                    target_distance = round(week_easy_run_km * 1.2, 1)
                    target_pace = paces.get('E', 360)
                    desc = "Build aerobic engine with an easy effort."
                elif phase == "Specific":
                    # Alternate T and I
                    if week % 2 == 0:
                        workout_type = "Intervals"
                        title = "VMA Intervals (I)"
                        target_distance = round(week_quality_km, 1)
                        target_pace = paces.get('I', 300)
                        reps = int(target_distance / 0.8)
                        desc = f"{reps}x800m at I pace with 400m recovery. Warmup/cooldown included."
                    else:
                        workout_type = "Threshold"
                        title = "Tempo Run (T)"
                        target_distance = round(week_quality_km, 1)
                        target_pace = paces.get('T', 300)
                        desc = f"Warmup, {round(target_distance*0.6, 1)}km at T pace, cooldown."
                elif phase == "Taper":
                    workout_type = "Race Pace"
                    title = "Goal Pace Run (M)"
                    target_distance = round(week_quality_km * 0.8, 1)
                    target_pace = paces.get('M', 300)
                    desc = f"Practice race pace. Stay relaxed."
            else:
                workout_type = "Easy"
                title = "Recovery Run (E)"
                target_distance = round(week_easy_run_km, 1)
                target_pace = paces.get('E', 360)
                desc = "Easy recovery run. Very relaxed pace."

            workouts.append({
                "week_number": week,
                "day_of_week": day_of_week,
                "workout_date": day_date.strftime("%Y-%m-%d"),
                "workout_type": workout_type,
                "title": title,
                "description": desc,
                "target_distance_km": target_distance,
                "target_pace_sec_per_km": target_pace
            })

    # Ensure race day is in the plan
    race_day_workout = None
    for w in workouts:
        if w['workout_date'] == race_date_str:
            race_day_workout = w
            break

    if race_day_workout:
        # Override existing workout on race day
        race_day_workout['workout_type'] = "Race"
        race_day_workout['title'] = "Race Day!"
        race_day_workout['description'] = f"Go crush your {goal_distance_km}km goal!"
        race_day_workout['target_distance_km'] = goal_distance_km
        race_day_workout['target_pace_sec_per_km'] = paces.get('M', 0)
    else:
        # Race day didn't get a workout (not an available day) — add it anyway
        race_week = math.ceil((race_date - start_date).days / 7)
        workouts.append({
            "week_number": max(1, race_week),
            "day_of_week": race_date.weekday(),
            "workout_date": race_date_str,
            "workout_type": "Race",
            "title": "Race Day!",
            "description": f"Go crush your {goal_distance_km}km goal!",
            "target_distance_km": goal_distance_km,
            "target_pace_sec_per_km": paces.get('M', 0)
        })

    return {
        "user_id": user_id,
        "start_date": start_date_str,
        "end_date": race_date_str,
        "total_weeks": total_weeks,
        "plan_type": plan_type,
        "workouts": workouts
    }

if __name__ == "__main__":
    import json
    vdot = get_paces_from_vdot(50.0)
    plan = generate_plan(1, "2024-05-01", "2024-07-25", 21.1, 50.0, [0, 2, 4, 6]) # Mon, Wed, Fri, Sun
    print(f"Plan Type: {plan.get('plan_type')}")
    print(f"Total Weeks: {plan.get('total_weeks')}")
    print(f"Workouts generated: {len(plan.get('workouts', []))}")
    if plan.get('workouts'):
        print(json.dumps(plan['workouts'][0], indent=2))
        print(json.dumps(plan['workouts'][-1], indent=2))
