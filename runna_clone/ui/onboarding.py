import flet as ft
from core.vdot_calc import calculate_vdot_from_race
from database.db_manager import get_db
import datetime

class Onboarding(ft.Container):
    def __init__(self, page: ft.Page, on_complete):
        super().__init__()
        self._page = page
        self.on_complete = on_complete
        self.padding = 40
        self.alignment = ft.Alignment(0, 0)

        # State variables
        self.ref_distance_dd = ft.Dropdown(
            label="Reference Distance",
            options=[
                ft.dropdown.Option("5k", "5 Kilometers (5k)"),
                ft.dropdown.Option("10k", "10 Kilometers (10k)"),
            ],
            value="5k",
            width=300
        )
        self.ref_time_tf = ft.TextField(label="Recent Time (MM:SS)", width=300, hint_text="e.g., 22:30")

        self.goal_distance_dd = ft.Dropdown(
            label="Goal Distance",
            options=[
                ft.dropdown.Option("5.0", "5k"),
                ft.dropdown.Option("10.0", "10k"),
                ft.dropdown.Option("21.1", "Half Marathon (21.1k)"),
                ft.dropdown.Option("42.2", "Marathon (42.2k)"),
            ],
            value="21.1",
            width=300
        )
        self.goal_time_tf = ft.TextField(label="Goal Time (HH:MM:SS) Optional", width=300, hint_text="e.g., 01:45:00")

        self.race_date_tf = ft.TextField(label="Race Date (YYYY-MM-DD)", width=300, hint_text="e.g., 2024-10-15")

        # Available days checkboxes
        self.days_checks = [
            ft.Checkbox(label="Mon", value=True, data=0),
            ft.Checkbox(label="Tue", value=False, data=1),
            ft.Checkbox(label="Wed", value=True, data=2),
            ft.Checkbox(label="Thu", value=False, data=3),
            ft.Checkbox(label="Fri", value=True, data=4),
            ft.Checkbox(label="Sat", value=False, data=5),
            ft.Checkbox(label="Sun", value=True, data=6),
        ]

        self.error_text = ft.Text(color=ft.Colors.RED_400, visible=False)

        self.content = ft.Column(
            controls=[
                ft.Text("Welcome to Runna Clone!", size=32, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700),
                ft.Text("Let's personalize your training plan.", size=16, color=ft.Colors.GREY_700),
                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),

                ft.Text("1. Current Fitness", size=20, weight=ft.FontWeight.W_600),
                self.ref_distance_dd,
                self.ref_time_tf,

                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                ft.Text("2. Your Goal", size=20, weight=ft.FontWeight.W_600),
                self.goal_distance_dd,
                self.goal_time_tf,
                self.race_date_tf,

                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                ft.Text("3. Available Days to Run", size=20, weight=ft.FontWeight.W_600),
                ft.Row(controls=self.days_checks, wrap=True, width=400),

                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                self.error_text,
                ft.ElevatedButton(
                    "Generate My Plan",
                    icon=ft.Icons.DIRECTIONS_RUN,
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE,
                        bgcolor=ft.Colors.GREEN_600,
                        padding=20,
                    ),
                    on_click=self.submit_form
                )
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
        )

    def parse_time(self, time_str: str) -> int:
        """Parses MM:SS or HH:MM:SS to total seconds."""
        parts = time_str.strip().split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return 0

    def show_error(self, message: str):
        """Displays a user-friendly error message."""
        self.error_text.value = message
        self.error_text.visible = True
        self._page.update()

    def submit_form(self, e):
        self.error_text.visible = False
        self._page.update()

        # --- Validate Reference Time ---
        ref_time_raw = self.ref_time_tf.value.strip()
        if not ref_time_raw:
            self.show_error("Please enter your recent race time (e.g., 22:30).")
            return

        try:
            ref_time_sec = self.parse_time(ref_time_raw)
        except (ValueError, IndexError):
            self.show_error("Invalid time format. Use MM:SS (e.g., 22:30).")
            return

        if ref_time_sec <= 0:
            self.show_error("Race time must be greater than zero.")
            return

        # --- Validate Race Date ---
        race_date_raw = self.race_date_tf.value.strip()
        if not race_date_raw:
            self.show_error("Please enter your race date (YYYY-MM-DD).")
            return

        try:
            race_date = datetime.datetime.strptime(race_date_raw, "%Y-%m-%d").date()
        except ValueError:
            self.show_error("Invalid date format. Please use YYYY-MM-DD (e.g., 2024-10-15).")
            return

        if race_date <= datetime.date.today():
            self.show_error("Race date must be in the future.")
            return

        # --- Validate Available Days ---
        avail_days = [cb.data for cb in self.days_checks if cb.value]
        if not avail_days:
            self.show_error("Please select at least one running day.")
            return

        # --- All validations passed — calculate & save ---
        try:
            ref_dist = 5000 if self.ref_distance_dd.value == "5k" else 10000
            vdot = calculate_vdot_from_race(ref_dist, ref_time_sec)

            goal_dist_km = float(self.goal_distance_dd.value)
            goal_time_sec = self.parse_time(self.goal_time_tf.value) if self.goal_time_tf.value.strip() else 0

            days_str = ",".join(map(str, avail_days))

            with get_db() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO users (
                        current_5k_time_sec, current_10k_time_sec, goal_distance_km, goal_time_sec, race_date, available_days, vdot
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    ref_time_sec if ref_dist == 5000 else None,
                    ref_time_sec if ref_dist == 10000 else None,
                    goal_dist_km,
                    goal_time_sec,
                    race_date_raw,
                    days_str,
                    vdot
                ))
                user_id = cursor.lastrowid

                # Init gamification for user
                cursor.execute('INSERT INTO gamification (user_id) VALUES (?)', (user_id,))

            self.on_complete(user_id)

        except Exception as ex:
            self.show_error(f"Something went wrong: {str(ex)}")
