import flet as ft
from database.db_manager import init_db, get_connection
from ui.onboarding import Onboarding
from ui.dashboard import Dashboard
from core.plan_engine import generate_plan
import datetime

def main(page: ft.Page):
    page.title = "Runna Clone"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.padding = 20

    init_db()

    def check_existing_user():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users ORDER BY created_at DESC LIMIT 1")
        user = cursor.fetchone()
        conn.close()
        return user[0] if user else None

    def on_onboarding_complete(user_id):
        # Fetch user data to generate plan
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT goal_distance_km, race_date, available_days, vdot FROM users WHERE id = ?", (user_id,))
        user_data = cursor.fetchone()

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
            # Save plan to DB
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
                ''', (plan_id, w['week_number'], w['day_of_week'], w['workout_date'], w['workout_type'], w['title'], w['description'], w['target_distance_km'], w['target_pace_sec_per_km']))

            conn.commit()

        conn.close()

        show_dashboard(user_id)

    def show_dashboard(user_id):
        page.controls.clear()

        # Header App Bar
        page.appbar = ft.AppBar(
            title=ft.Text("Runna Clone", color=ft.Colors.WHITE),
            center_title=True,
            bgcolor=ft.Colors.BLUE_700,
            actions=[
                ft.IconButton(ft.icons.RESTART_ALT, on_click=lambda e: reset_app(), tooltip="Reset App Data")
            ]
        )

        dashboard_view = Dashboard(page, user_id=user_id)
        page.add(dashboard_view.content)
        page.update()

    def reset_app():
        # Quick and dirty way to reset for testing
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM workouts")
        c.execute("DELETE FROM training_plans")
        c.execute("DELETE FROM gamification")
        c.execute("DELETE FROM users")
        conn.commit()
        conn.close()
        page.appbar = None
        show_onboarding()

    def show_onboarding():
        page.controls.clear()
        onboarding_view = Onboarding(page, on_complete=on_onboarding_complete)
        page.add(onboarding_view.content)
        page.update()

    # App Entry Point
    user_id = check_existing_user()
    if user_id:
        show_dashboard(user_id)
    else:
        show_onboarding()

if __name__ == "__main__":
    ft.app(main)
