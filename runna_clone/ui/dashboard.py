import flet as ft
from database.db_manager import get_db
from ui.components import CircularProgressBar, WorkoutCard
import datetime

class Dashboard(ft.Container):
    def __init__(self, page: ft.Page, user_id: int):
        super().__init__()
        self._page = page
        self.user_id = user_id
        self.padding = 20
        self.expand = True

        self.current_week = 1

        self.header_row = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        self.stats_row = ft.Row(alignment=ft.MainAxisAlignment.SPACE_EVENLY)
        self.workouts_column = ft.Column(spacing=15, scroll=ft.ScrollMode.AUTO)
        self.motivation_text = ft.Text(size=18, italic=True, color=ft.Colors.ORANGE_700)

        self.progress_bar = CircularProgressBar(value=0.0, color=ft.Colors.BLUE, size=120)

        # Store the week label as an instance variable so it can be updated
        self.week_label = ft.Text(f"Week {self.current_week}", size=24, weight=ft.FontWeight.BOLD)

        self.content = ft.Column(
            controls=[
                self.header_row,
                ft.Divider(height=2),
                ft.Text("Weekly Progress", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            self.progress_bar,
                            ft.Column([
                                self.motivation_text,
                                self.stats_row,
                            ], alignment=ft.MainAxisAlignment.CENTER)
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        spacing=40
                    ),
                    padding=20,
                    bgcolor=ft.Colors.GREY_50,
                    border_radius=10,
                ),
                ft.Divider(height=20),
                ft.Row(
                    controls=[
                        ft.IconButton(ft.Icons.ARROW_BACK, on_click=self.prev_week),
                        self.week_label,
                        ft.IconButton(ft.Icons.ARROW_FORWARD, on_click=self.next_week),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER
                ),
                self.workouts_column
            ]
        )

        self.load_data()

    def get_plan_id(self):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM training_plans WHERE user_id = ? ORDER BY created_at DESC LIMIT 1', (self.user_id,))
            row = cursor.fetchone()
            return row[0] if row else None

    def load_data(self):
        plan_id = self.get_plan_id()
        if not plan_id:
            self.workouts_column.controls.clear()
            self.workouts_column.controls.append(ft.Text("No active training plan found.", color=ft.Colors.RED))
            return

        # Update the week label text
        self.week_label.value = f"Week {self.current_week}"

        with get_db() as conn:
            cursor = conn.cursor()

            # Load user stats
            cursor.execute('SELECT current_streak, total_workouts_completed FROM gamification WHERE user_id = ?', (self.user_id,))
            stats = cursor.fetchone()
            if stats:
                streak, total_completed = stats
                self.stats_row.controls = [
                    ft.Column([ft.Icon(ft.Icons.LOCAL_FIRE_DEPARTMENT, color=ft.Colors.ORANGE), ft.Text(f"{streak} Day Streak", weight=ft.FontWeight.BOLD)]),
                    ft.Column([ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN), ft.Text(f"{total_completed} Total Runs", weight=ft.FontWeight.BOLD)])
                ]
                if streak > 0:
                    self.motivation_text.value = "You're on fire! Keep it up!"
                else:
                    self.motivation_text.value = "Let's get started on your goals!"
            else:
                self.motivation_text.value = "Let's get started on your goals!"

            # Load workouts for current week
            cursor.execute('SELECT id, workout_date, workout_type, title, description, target_distance_km, target_pace_sec_per_km, status FROM workouts WHERE plan_id = ? AND week_number = ? ORDER BY workout_date ASC', (plan_id, self.current_week))

            workouts = []
            for row in cursor.fetchall():
                workouts.append({
                    'id': row[0],
                    'workout_date': row[1],
                    'workout_type': row[2],
                    'title': row[3],
                    'description': row[4],
                    'target_distance_km': row[5],
                    'target_pace_sec_per_km': row[6],
                    'status': row[7]
                })

        self.workouts_column.controls.clear()

        completed_count = 0
        total_count = len(workouts)

        for w in workouts:
            if w['status'] == 'completed':
                completed_count += 1
            self.workouts_column.controls.append(WorkoutCard(w, self.on_workout_status_change))

        progress = (completed_count / total_count) if total_count > 0 else 0.0
        self.progress_bar.update_progress(progress)

        self.update()

    def prev_week(self, e):
        if self.current_week > 1:
            self.current_week -= 1
            self.load_data()

    def next_week(self, e):
        plan_id = self.get_plan_id()
        if not plan_id:
            return

        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT total_weeks FROM training_plans WHERE id = ?", (plan_id,))
            row = c.fetchone()
            if not row:
                return
            total_weeks = row[0]

        if self.current_week < total_weeks:
            self.current_week += 1
            self.load_data()

    def on_workout_status_change(self, workout_id, is_completed):
        status = 'completed' if is_completed else 'pending'

        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute('UPDATE workouts SET status = ?, completed_at = ? WHERE id = ?',
                           (status, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") if is_completed else None, workout_id))

            # Recalculate gamification from actual data instead of naive increment/decrement
            self._recalculate_gamification(conn)

        self.load_data()

    def _recalculate_gamification(self, conn):
        """Recalculates streak and total from actual workout data."""
        cursor = conn.cursor()

        # Find plan_id for this user
        cursor.execute('SELECT id FROM training_plans WHERE user_id = ? ORDER BY created_at DESC LIMIT 1', (self.user_id,))
        plan_row = cursor.fetchone()
        if not plan_row:
            return
        plan_id = plan_row[0]

        # Count total completed workouts
        cursor.execute('SELECT COUNT(*) FROM workouts WHERE plan_id = ? AND status = ?', (plan_id, 'completed'))
        total_completed = cursor.fetchone()[0]

        # Calculate streak: count consecutive completed workouts going backwards
        # from the most recent past workout date
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        cursor.execute('''
            SELECT status FROM workouts
            WHERE plan_id = ? AND workout_date <= ?
            ORDER BY workout_date DESC
        ''', (plan_id, today_str))

        streak = 0
        for row in cursor.fetchall():
            if row[0] == 'completed':
                streak += 1
            else:
                break

        # Update gamification, preserving longest_streak
        cursor.execute('''
            UPDATE gamification
            SET current_streak = ?,
                total_workouts_completed = ?,
                longest_streak = MAX(longest_streak, ?)
            WHERE user_id = ?
        ''', (streak, total_completed, streak, self.user_id))
