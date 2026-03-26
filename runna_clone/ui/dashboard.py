import flet as ft
from database.db_manager import get_connection
from ui.components import CircularProgressBar, WorkoutCard
import datetime

class Dashboard(ft.Container):
    def __init__(self, page: ft.Page, user_id: int):
        super().__init__()
        self.page = page
        self.user_id = user_id
        self.padding = 20
        self.expand = True

        self.current_week = 1

        self.header_row = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        self.stats_row = ft.Row(alignment=ft.MainAxisAlignment.SPACE_EVENLY)
        self.workouts_column = ft.Column(spacing=15, scroll=ft.ScrollMode.AUTO)
        self.motivation_text = ft.Text(size=18, italic=True, color=ft.Colors.ORANGE_700)

        self.progress_bar = CircularProgressBar(value=0.0, color=ft.Colors.BLUE, size=120)

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
                        ft.IconButton(ft.icons.ARROW_BACK, on_click=self.prev_week),
                        ft.Text(f"Week {self.current_week}", size=24, weight=ft.FontWeight.BOLD),
                        ft.IconButton(ft.icons.ARROW_FORWARD, on_click=self.next_week),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER
                ),
                self.workouts_column
            ]
        )

        self.load_data()

    def get_plan_id(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM training_plans WHERE user_id = ? ORDER BY created_at DESC LIMIT 1', (self.user_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def load_data(self):
        plan_id = self.get_plan_id()
        if not plan_id:
            self.workouts_column.controls.append(ft.Text("No active training plan found.", color=ft.Colors.RED))
            return

        conn = get_connection()
        cursor = conn.cursor()

        # Load user stats
        cursor.execute('SELECT current_streak, total_workouts_completed FROM gamification WHERE user_id = ?', (self.user_id,))
        stats = cursor.fetchone()
        if stats:
            streak, total_completed = stats
            self.stats_row.controls = [
                ft.Column([ft.Icon(ft.icons.LOCAL_FIRE_DEPARTMENT, color=ft.Colors.ORANGE), ft.Text(f"{streak} Day Streak", weight=ft.FontWeight.BOLD)]),
                ft.Column([ft.Icon(ft.icons.CHECK_CIRCLE, color=ft.Colors.GREEN), ft.Text(f"{total_completed} Total Runs", weight=ft.FontWeight.BOLD)])
            ]
            if streak > 0:
                self.motivation_text.value = f"You're on fire! Keep it up!"
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

        conn.close()

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
        # We don't have total_weeks in memory easily without a query,
        # let's assume if there are workouts we can go forward or we could fetch total_weeks
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT total_weeks FROM training_plans WHERE id = ?", (self.get_plan_id(),))
        total_weeks = c.fetchone()[0]
        conn.close()

        if self.current_week < total_weeks:
            self.current_week += 1
            self.load_data()

    def on_workout_status_change(self, workout_id, is_completed):
        status = 'completed' if is_completed else 'pending'

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('UPDATE workouts SET status = ?, completed_at = ? WHERE id = ?',
                       (status, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") if is_completed else None, workout_id))

        # Update streak logically
        # Simplified: increment total completed, update streak based on today
        if is_completed:
            cursor.execute('UPDATE gamification SET total_workouts_completed = total_workouts_completed + 1, current_streak = current_streak + 1 WHERE user_id = ?', (self.user_id,))
        else:
            # Reverting
            cursor.execute('UPDATE gamification SET total_workouts_completed = MAX(0, total_workouts_completed - 1), current_streak = MAX(0, current_streak - 1) WHERE user_id = ?', (self.user_id,))

        conn.commit()
        conn.close()

        self.load_data()
