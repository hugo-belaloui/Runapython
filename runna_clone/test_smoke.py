"""Quick smoke test for all modules."""
import sys

print("=== Testing db_manager ===")
from database.db_manager import init_db, get_db
init_db()
print("  DB initialized OK")

with get_db() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cursor.fetchall()]
    print(f"  Tables: {tables}")

print("\n=== Testing vdot_calc ===")
from core.vdot_calc import calculate_vdot_from_race, get_paces_from_vdot, format_pace
vdot = calculate_vdot_from_race(5000, 20 * 60)  # 20 min 5k
print(f"  VDOT for 20min 5k: {vdot:.1f}")
paces = get_paces_from_vdot(vdot)
for k, v in paces.items():
    print(f"  {k} Pace: {format_pace(v)}/km")

print("\n=== Testing plan_engine ===")
from core.plan_engine import generate_plan
plan = generate_plan(1, "2026-04-18", "2026-07-18", 21.1, vdot, [0, 2, 4, 6])
print(f"  Plan type: {plan['plan_type']}")
print(f"  Total weeks: {plan['total_weeks']}")
print(f"  Workouts: {len(plan['workouts'])}")
print(f"  First: {plan['workouts'][0]['title']} on {plan['workouts'][0]['workout_date']}")
print(f"  Last:  {plan['workouts'][-1]['title']} on {plan['workouts'][-1]['workout_date']}")

# Check race day is included
race_workouts = [w for w in plan['workouts'] if w['workout_type'] == 'Race']
if race_workouts:
    print(f"  Race day: {race_workouts[0]['workout_date']} OK")
else:
    print("  WARNING: Race day NOT found in plan!")

print("\n=== Testing plan_service ===")
from core.plan_service import create_plan_for_user
# This needs a real user in DB, so just check the import works
print("  Import OK")

print("\n=== All tests passed! ===")
