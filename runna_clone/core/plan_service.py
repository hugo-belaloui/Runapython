import datetime
from database.db_manager import get_db
from core.plan_engine import generate_plan


def create_plan_for_user(user_id: int) -> dict:
    """Fetches user data and generates + saves a full training plan."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT goal_distance_km, race_date, available_days, vdot FROM users WHERE id = ?",
            (user_id,)
        )
        user_data = cursor.fetchone()

        if not user_data:
            return {"error": "User not found."}

        goal_distance_km, race_date_str, available_days_str, vdot = user_data
        available_days = [int(x) for x in available_days_str.split(',')]
        start_date_str = datetime.date.today().strftime("%Y-%m-%d")

        plan = generate_plan(
            user_id=user_id,
            start_date_str=start_date_str,
            race_date_str=race_date_str,
            goal_distance_km=goal_distance_km,
            vdot=vdot,
            available_days=available_days
        )

        if "error" not in plan:
            # Save training plan
            cursor.execute('''
                INSERT INTO training_plans (user_id, start_date, end_date, total_weeks, plan_type)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, plan['start_date'], plan['end_date'], plan['total_weeks'], plan['plan_type']))

            plan_id = cursor.lastrowid

            # Save workouts
            for w in plan['workouts']:
                cursor.execute('''
                    INSERT INTO workouts (plan_id, week_number, day_of_week, workout_date, workout_type, title, description, target_distance_km, target_pace_sec_per_km)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (plan_id, w['week_number'], w['day_of_week'], w['workout_date'],
                      w['workout_type'], w['title'], w['description'],
                      w['target_distance_km'], w['target_pace_sec_per_km']))

        return plan
