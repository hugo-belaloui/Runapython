import flet as ft
from database.db_manager import init_db, get_db
from ui.onboarding import Onboarding
from ui.dashboard import Dashboard
from core.plan_service import create_plan_for_user

def main(page: ft.Page):
    page.title = "Runna Clone"
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.padding = 20

    init_db()

    def check_existing_user():
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users ORDER BY created_at DESC LIMIT 1")
            user = cursor.fetchone()
            return user[0] if user else None

    def on_onboarding_complete(user_id):
        plan = create_plan_for_user(user_id)

        if plan.get("error"):
            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Could not generate plan: {plan['error']}"),
                bgcolor=ft.Colors.RED_400
            )
            page.snack_bar.open = True
            page.update()
            return

        show_dashboard(user_id)

    def show_dashboard(user_id):
        page.controls.clear()

        # Header App Bar
        page.appbar = ft.AppBar(
            title=ft.Text("Runna Clone", color=ft.Colors.WHITE),
            center_title=True,
            bgcolor=ft.Colors.BLUE_700,
            actions=[
                ft.IconButton(ft.Icons.RESTART_ALT, on_click=lambda e: confirm_reset(), tooltip="Reset App Data")
            ]
        )

        dashboard_view = Dashboard(page, user_id=user_id)
        page.add(dashboard_view.content)
        page.update()

    def confirm_reset():
        """Shows a confirmation dialog before wiping all data."""
        def do_reset(e):
            dialog.open = False
            page.update()

            with get_db() as conn:
                c = conn.cursor()
                c.execute("DELETE FROM workouts")
                c.execute("DELETE FROM training_plans")
                c.execute("DELETE FROM gamification")
                c.execute("DELETE FROM users")

            page.appbar = None
            show_onboarding()

        def cancel(e):
            dialog.open = False
            page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Reset All Data?"),
            content=ft.Text("This will permanently delete all your training data. This cannot be undone."),
            actions=[
                ft.TextButton("Cancel", on_click=cancel),
                ft.TextButton("Reset", on_click=do_reset, style=ft.ButtonStyle(color=ft.Colors.RED)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.dialog = dialog
        dialog.open = True
        page.update()

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
    ft.run(main)
