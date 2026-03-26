import flet as ft
from core.vdot_calc import format_pace

class CircularProgressBar(ft.Stack):
    def __init__(self, value=0.0, color=ft.Colors.BLUE, size=100, stroke_width=8):
        super().__init__()
        self.size = size
        self.width = size
        self.height = size

        self.progress_ring = ft.ProgressRing(
            value=value,
            color=color,
            bgcolor=ft.Colors.GREY_200,
            stroke_width=stroke_width,
            width=size,
            height=size
        )

        self.percentage_text = ft.Text(
            f"{int(value * 100)}%",
            size=size*0.25,
            weight=ft.FontWeight.BOLD,
            color=color
        )

        self.controls = [
            self.progress_ring,
            ft.Container(
                content=self.percentage_text,
                alignment=ft.alignment.center,
                width=size,
                height=size
            )
        ]

    def update_progress(self, new_value):
        self.progress_ring.value = new_value
        self.percentage_text.value = f"{int(new_value * 100)}%"
        self.update()


class WorkoutCard(ft.Card):
    def __init__(self, workout_data: dict, on_complete_click):
        super().__init__()
        self.workout_data = workout_data
        self.elevation = 4

        status = workout_data.get('status', 'pending')
        is_completed = status == 'completed'

        card_color = ft.Colors.GREEN_50 if is_completed else ft.Colors.WHITE
        border_color = ft.Colors.GREEN if is_completed else ft.Colors.GREY_300

        self.checkbox = ft.Checkbox(
            value=is_completed,
            fill_color=ft.Colors.GREEN,
            on_change=lambda e: on_complete_click(self.workout_data['id'], e.control.value)
        )

        pace_str = format_pace(workout_data.get('target_pace_sec_per_km', 0))
        dist_km = workout_data.get('target_distance_km', 0)

        self.content = ft.Container(
            bgcolor=card_color,
            border=ft.border.all(1, border_color),
            border_radius=10,
            padding=15,
            content=ft.Row(
                controls=[
                    self.checkbox,
                    ft.Column(
                        controls=[
                            ft.Text(f"{workout_data['workout_date']} - {workout_data['workout_type']}", size=12, color=ft.Colors.GREY),
                            ft.Text(workout_data['title'], size=16, weight=ft.FontWeight.BOLD),
                            ft.Text(f"Target: {dist_km}km @ {pace_str}/km", size=14, color=ft.Colors.BLUE_700),
                            ft.Text(workout_data['description'], size=12, italic=True),
                        ],
                        expand=True
                    )
                ]
            )
        )
