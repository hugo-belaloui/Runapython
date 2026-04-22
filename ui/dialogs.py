"""
Modal dialogs for Runna — welcome wizard, plan generation, session details,
pace calculator.
"""

from __future__ import annotations

from datetime import date, timedelta

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox, QPushButton,
    QDialogButtonBox, QGroupBox, QGridLayout, QTextEdit, QFrame,
    QMessageBox, QWidget,
)

from core.models import PlanInputs, PaceZone, Session, FullPlan, RACE_DISTANCES
from core.training_engine import (
    calculate_vdot, vdot_to_pace_zones, generate_full_plan, vdot_to_race_prediction,
)
from ui.styles import (
    DIALOG_STYLE, ZONE_COLORS, format_pace, format_time,
)


# ═══════════════════════════════════════════════════════════════════════════
# Welcome / First-Run Setup Dialog
# ═══════════════════════════════════════════════════════════════════════════

class WelcomeDialog(QDialog):
    """
    First-run welcome wizard — shown when the database has no plans.
    Collects user inputs and generates their first training plan.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Runna")
        self.setMinimumSize(560, 740)
        self.setStyleSheet(DIALOG_STYLE)
        self.generated_plan: FullPlan | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(28, 28, 28, 28)

        # Hero section
        hero = QLabel("🏃")
        hero.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero.setStyleSheet("font-size: 52px; padding: 8px 0;")
        layout.addWidget(hero)

        title = QLabel("Welcome to Runna")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #1A1A2E; margin-bottom: 2px;")
        layout.addWidget(title)

        subtitle = QLabel("Let's build your personalized training plan.\n"
                          "Tell us about your race goal and current fitness.")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #666; font-size: 14px; margin-bottom: 12px;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # ── Race details group ──
        race_group = QGroupBox("🏆  Race Goal")
        race_form = QFormLayout(race_group)
        race_form.setSpacing(10)
        race_form.setContentsMargins(16, 28, 16, 16)

        self.race_distance_combo = QComboBox()
        self.race_distance_combo.addItems(["5K", "10K", "HM", "Marathon"])
        self.race_distance_combo.setCurrentText("10K")
        race_form.addRow("Race Distance:", self.race_distance_combo)

        self.race_date_edit = QDateEdit()
        self.race_date_edit.setCalendarPopup(True)
        self.race_date_edit.setDate(QDate.currentDate().addDays(84))
        self.race_date_edit.setMinimumDate(QDate.currentDate().addDays(28))
        race_form.addRow("Race Date:", self.race_date_edit)

        layout.addWidget(race_group)

        # ── Current fitness group ──
        fitness_group = QGroupBox("💪  Current Fitness")
        fitness_form = QFormLayout(fitness_group)
        fitness_form.setSpacing(10)
        fitness_form.setContentsMargins(16, 28, 16, 16)

        self.weekly_km_spin = QDoubleSpinBox()
        self.weekly_km_spin.setRange(5, 200)
        self.weekly_km_spin.setValue(25.0)
        self.weekly_km_spin.setSuffix(" km")
        self.weekly_km_spin.setSingleStep(5)
        fitness_form.addRow("Current Weekly Km:", self.weekly_km_spin)

        self.recent_race_combo = QComboBox()
        self.recent_race_combo.addItems(["5K", "10K", "HM", "Marathon"])
        self.recent_race_combo.setCurrentText("5K")
        fitness_form.addRow("Recent Race Distance:", self.recent_race_combo)

        # Race time input
        time_layout = QHBoxLayout()
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(6)

        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(0, 10)
        self.hours_spin.setValue(0)
        self.hours_spin.setSuffix(" h")
        time_layout.addWidget(self.hours_spin)

        self.mins_spin = QSpinBox()
        self.mins_spin.setRange(0, 59)
        self.mins_spin.setValue(25)
        self.mins_spin.setSuffix(" m")
        time_layout.addWidget(self.mins_spin)

        self.secs_spin = QSpinBox()
        self.secs_spin.setRange(0, 59)
        self.secs_spin.setValue(0)
        self.secs_spin.setSuffix(" s")
        time_layout.addWidget(self.secs_spin)
        time_layout.addStretch()

        fitness_form.addRow("Recent Race Time:", time_layout)

        layout.addWidget(fitness_group)

        # ── Schedule group ──
        sched_group = QGroupBox("🗓  Schedule")
        sched_form = QFormLayout(sched_group)
        sched_form.setSpacing(10)
        sched_form.setContentsMargins(16, 28, 16, 16)

        self.days_spin = QSpinBox()
        self.days_spin.setRange(3, 7)
        self.days_spin.setValue(4)
        self.days_spin.setSuffix(" days/week")
        sched_form.addRow("Days Per Week:", self.days_spin)

        self.long_run_combo = QComboBox()
        days = ["Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", "Sunday"]
        self.long_run_combo.addItems(days)
        self.long_run_combo.setCurrentIndex(6)  # Sunday
        sched_form.addRow("Long Run Day:", self.long_run_combo)

        layout.addWidget(sched_group)

        layout.addStretch()

        # ── Button ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        start_btn = QPushButton("🚀  Create My Plan")
        start_btn.setObjectName("primaryBtn")
        start_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6C63FF, stop:1 #8B5CF6);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 32px;
                font-size: 15px;
                font-weight: 700;
                min-height: 40px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5B52E0, stop:1 #7C4FE0);
            }
        """)
        start_btn.clicked.connect(self._on_create)
        btn_layout.addWidget(start_btn)

        layout.addLayout(btn_layout)

    def _get_race_time_seconds(self) -> int:
        return (self.hours_spin.value() * 3600
                + self.mins_spin.value() * 60
                + self.secs_spin.value())

    def _on_create(self):
        race_time = self._get_race_time_seconds()
        if race_time < 60:
            QMessageBox.warning(self, "Invalid Input",
                                "Please enter a valid race time (at least 1 minute).")
            return

        race_date_q = self.race_date_edit.date()
        race_date_py = date(race_date_q.year(), race_date_q.month(), race_date_q.day())

        inputs = PlanInputs(
            race_distance=self.race_distance_combo.currentText(),
            race_date=race_date_py,
            current_weekly_km=self.weekly_km_spin.value(),
            recent_race_distance=self.recent_race_combo.currentText(),
            recent_race_time_seconds=race_time,
            days_per_week=self.days_spin.value(),
            long_run_day=self.long_run_combo.currentIndex(),
        )

        try:
            self.generated_plan = generate_full_plan(inputs)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Plan generation failed:\n{e}")
            return

        self.accept()


# ═══════════════════════════════════════════════════════════════════════════
# Plan Generation Dialog
# ═══════════════════════════════════════════════════════════════════════════

class PlanGenerationDialog(QDialog):
    """Full plan creation wizard — collects PlanInputs, shows preview, saves."""

    def __init__(self, parent=None, initial_inputs: PlanInputs | None = None):
        super().__init__(parent)
        self.setWindowTitle("Generate Training Plan")
        self.setMinimumSize(520, 680)
        self.setStyleSheet(DIALOG_STYLE)
        self.generated_plan: FullPlan | None = None
        self.initial_inputs = initial_inputs

        self._build_ui()
        if self.initial_inputs:
            self._fill_initial_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("🏃  New Training Plan")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #1A1A2E; margin-bottom: 4px;")
        layout.addWidget(title)

        subtitle = QLabel("Fill in your details to generate a personalized plan")
        subtitle.setStyleSheet("color: #555; font-size: 13px; margin-bottom: 8px;")
        layout.addWidget(subtitle)

        # ── Race details group ──
        race_group = QGroupBox("Race Details")
        race_form = QFormLayout(race_group)
        race_form.setSpacing(10)
        race_form.setContentsMargins(16, 24, 16, 16)

        self.race_distance_combo = QComboBox()
        self.race_distance_combo.addItems(["5K", "10K", "HM", "Marathon"])
        self.race_distance_combo.setCurrentText("Marathon")
        race_form.addRow("Race Distance:", self.race_distance_combo)

        self.race_date_edit = QDateEdit()
        self.race_date_edit.setCalendarPopup(True)
        self.race_date_edit.setDate(QDate.currentDate().addDays(84))  # ~12 weeks
        self.race_date_edit.setMinimumDate(QDate.currentDate().addDays(28))
        race_form.addRow("Race Date:", self.race_date_edit)

        layout.addWidget(race_group)

        # ── Current fitness group ──
        fitness_group = QGroupBox("Current Fitness")
        fitness_form = QFormLayout(fitness_group)
        fitness_form.setSpacing(10)
        fitness_form.setContentsMargins(16, 24, 16, 16)

        self.weekly_km_spin = QDoubleSpinBox()
        self.weekly_km_spin.setRange(5, 200)
        self.weekly_km_spin.setValue(30.0)
        self.weekly_km_spin.setSuffix(" km")
        self.weekly_km_spin.setSingleStep(5)
        fitness_form.addRow("Current Weekly Km:", self.weekly_km_spin)

        self.recent_race_combo = QComboBox()
        self.recent_race_combo.addItems(["5K", "10K", "HM", "Marathon"])
        self.recent_race_combo.setCurrentText("5K")
        fitness_form.addRow("Recent Race Distance:", self.recent_race_combo)

        # Race time input — hours, minutes, seconds
        time_layout = QHBoxLayout()
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(4)

        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(0, 10)
        self.hours_spin.setValue(0)
        self.hours_spin.setSuffix(" h")
        time_layout.addWidget(self.hours_spin)

        self.mins_spin = QSpinBox()
        self.mins_spin.setRange(0, 59)
        self.mins_spin.setValue(25)
        self.mins_spin.setSuffix(" m")
        time_layout.addWidget(self.mins_spin)

        self.secs_spin = QSpinBox()
        self.secs_spin.setRange(0, 59)
        self.secs_spin.setValue(0)
        self.secs_spin.setSuffix(" s")
        time_layout.addWidget(self.secs_spin)
        time_layout.addStretch()

        fitness_form.addRow("Recent Race Time:", time_layout)

        layout.addWidget(fitness_group)

        # ── Schedule group ──
        sched_group = QGroupBox("Schedule Preferences")
        sched_form = QFormLayout(sched_group)
        sched_form.setSpacing(10)
        sched_form.setContentsMargins(16, 24, 16, 16)

        self.days_spin = QSpinBox()
        self.days_spin.setRange(3, 7)
        self.days_spin.setValue(5)
        self.days_spin.setSuffix(" days/week")
        sched_form.addRow("Days Per Week:", self.days_spin)

        self.long_run_combo = QComboBox()
        days = ["Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", "Sunday"]
        self.long_run_combo.addItems(days)
        self.long_run_combo.setCurrentIndex(6)  # Sunday
        sched_form.addRow("Long Run Day:", self.long_run_combo)

        layout.addWidget(sched_group)

        # ── Preview area (hidden initially) ──
        self.preview_group = QGroupBox("Plan Preview")
        self.preview_layout = QVBoxLayout(self.preview_group)
        self.preview_layout.setContentsMargins(16, 24, 16, 16)
        self.preview_label = QLabel("")
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("font-size: 13px; line-height: 1.5; color: #1A1A2E;")
        self.preview_layout.addWidget(self.preview_label)
        self.preview_group.hide()
        layout.addWidget(self.preview_group)

        # ── Buttons ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.generate_btn = QPushButton("⚡ Generate Plan")
        self.generate_btn.setObjectName("primaryBtn")
        self.generate_btn.clicked.connect(self._on_generate)
        btn_layout.addWidget(self.generate_btn)

        self.save_btn = QPushButton("💾 Save Plan")
        self.save_btn.setObjectName("primaryBtn")
        self.save_btn.clicked.connect(self.accept)
        self.save_btn.hide()
        btn_layout.addWidget(self.save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addStretch()
        layout.addLayout(btn_layout)

    def _fill_initial_values(self):
        if not self.initial_inputs:
            return
        ii = self.initial_inputs
        self.race_distance_combo.setCurrentText(ii.race_distance)
        self.race_date_edit.setDate(ii.race_date)
        self.weekly_km_spin.setValue(ii.current_weekly_km)
        self.recent_race_combo.setCurrentText(ii.recent_race_distance)
        
        h = ii.recent_race_time_seconds // 3600
        m = (ii.recent_race_time_seconds % 3600) // 60
        s = ii.recent_race_time_seconds % 60
        self.hours_spin.setValue(h)
        self.mins_spin.setValue(m)
        self.secs_spin.setValue(s)
        
        self.days_spin.setValue(ii.days_per_week)
        self.long_run_combo.setCurrentIndex(ii.long_run_day)

    def _get_race_time_seconds(self) -> int:
        return (self.hours_spin.value() * 3600
                + self.mins_spin.value() * 60
                + self.secs_spin.value())

    def _on_generate(self):
        """Generate plan from inputs and show preview."""
        race_time = self._get_race_time_seconds()
        if race_time < 60:
            QMessageBox.warning(self, "Invalid Input",
                                "Please enter a valid race time.")
            return

        race_date_q = self.race_date_edit.date()
        race_date_py = date(race_date_q.year(), race_date_q.month(), race_date_q.day())

        inputs = PlanInputs(
            race_distance=self.race_distance_combo.currentText(),
            race_date=race_date_py,
            current_weekly_km=self.weekly_km_spin.value(),
            recent_race_distance=self.recent_race_combo.currentText(),
            recent_race_time_seconds=race_time,
            days_per_week=self.days_spin.value(),
            long_run_day=self.long_run_combo.currentIndex(),
        )

        try:
            self.generated_plan = generate_full_plan(inputs)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Plan generation failed:\n{e}")
            return

        # Build preview text
        plan = self.generated_plan
        zones = plan.pace_zones
        zone_lines = []
        for z in zones:
            color = ZONE_COLORS.get(z.zone_name, "#333")
            zone_lines.append(
                f'<span style="color:{color}; font-weight:600;">● {z.zone_name}</span>: '
                f'{format_pace(z.min_pace_min_km)} – {format_pace(z.max_pace_min_km)} min/km'
            )

        # Race prediction
        race_dist_m = RACE_DISTANCES[plan.race_distance]
        predicted_time = vdot_to_race_prediction(plan.vdot, race_dist_m)

        preview_html = f"""
        <div style="font-size:14px; color: #1A1A2E;">
        <p><b>VDOT Score:</b> <span style="color:#6C63FF; font-size:20px; font-weight:bold;">
            {plan.vdot:.1f}</span></p>
        <p><b>Race Prediction ({plan.race_distance}):</b> {format_time(predicted_time)}</p>
        <p><b>Plan Duration:</b> {plan.total_weeks} weeks &nbsp;|&nbsp;
           <b>Total Sessions:</b> {plan.total_sessions}</p>
        <hr style="border-color:#E0E0E8;">
        <p><b>Pace Zones:</b></p>
        {'<br>'.join(zone_lines)}
        </div>
        """
        self.preview_label.setText(preview_html)
        self.preview_group.show()
        self.generate_btn.setText("🔄 Regenerate")
        self.save_btn.show()


# ═══════════════════════════════════════════════════════════════════════════
# Session Detail Dialog
# ═══════════════════════════════════════════════════════════════════════════

class SessionDetailDialog(QDialog):
    """Shows full session details and allows status changes."""

    SESSION_COLORS = {
        "Easy": "#22C55E",
        "Long Run": "#A855F7",
        "Tempo": "#F59E0B",
        "Intervals": "#EF4444",
        "Rest": "#9CA3AF",
        "Race": "#EC4899",
    }

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.new_status: str | None = None
        self.setWindowTitle(f"Session — {session.date.strftime('%A, %b %d')}")
        self.setMinimumSize(400, 380)
        self.setStyleSheet(DIALOG_STYLE)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        s = self.session
        color = self.SESSION_COLORS.get(s.session_type, "#333")

        # Header
        header = QLabel(f"<span style='color:{color}; font-size:22px; font-weight:bold;'>"
                        f"● {s.session_type}</span>")
        layout.addWidget(header)

        date_label = QLabel(s.date.strftime("%A, %B %d, %Y"))
        date_label.setStyleSheet("color: #555; font-size: 14px;")
        layout.addWidget(date_label)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #E0E0E8;")
        layout.addWidget(sep)

        # Details card
        details_group = QGroupBox("Details")
        details_form = QFormLayout(details_group)
        details_form.setSpacing(8)
        details_form.setContentsMargins(16, 24, 16, 16)

        dist_lbl = QLabel(f"{s.distance_km:.1f} km")
        dist_lbl.setStyleSheet("color: #1A1A2E; font-weight: 600;")
        details_form.addRow("Distance:", dist_lbl)

        pace_text = s.display_pace + " min/km" if s.pace_target_min_km else "—"
        pace_lbl = QLabel(pace_text)
        pace_lbl.setStyleSheet("color: #1A1A2E; font-weight: 600;")
        details_form.addRow("Target Pace:", pace_lbl)

        if s.pace_target_min_km and s.distance_km > 0:
            est_time = s.pace_target_min_km * s.distance_km
            dur_lbl = QLabel(format_time(est_time))
            dur_lbl.setStyleSheet("color: #1A1A2E; font-weight: 600;")
            details_form.addRow("Est. Duration:", dur_lbl)

        status_colors = {
            "planned": "#3B82F6",
            "completed": "#22C55E",
            "skipped": "#9CA3AF",
        }
        sc = status_colors.get(s.status, "#333")
        status_lbl = QLabel(
            f"<span style='color:{sc}; font-weight:600;'>"
            f"{s.status.upper()}</span>")
        details_form.addRow("Status:", status_lbl)

        layout.addWidget(details_group)

        # Notes
        if s.notes:
            notes_group = QGroupBox("Notes")
            notes_layout = QVBoxLayout(notes_group)
            notes_layout.setContentsMargins(16, 24, 16, 16)
            notes_label = QLabel(s.notes)
            notes_label.setWordWrap(True)
            notes_label.setStyleSheet("font-size: 13px; color: #333; line-height: 1.4;")
            notes_layout.addWidget(notes_label)
            layout.addWidget(notes_group)

        layout.addStretch()

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        if s.session_type != "Rest":
            complete_btn = QPushButton("✅ Mark Completed")
            complete_btn.setObjectName("primaryBtn")
            complete_btn.clicked.connect(lambda: self._set_status("completed"))
            btn_layout.addWidget(complete_btn)

            skip_btn = QPushButton("⏭ Skip")
            skip_btn.setObjectName("secondaryBtn")
            skip_btn.clicked.connect(lambda: self._set_status("skipped"))
            btn_layout.addWidget(skip_btn)

            if s.status != "planned":
                reset_btn = QPushButton("↩ Reset")
                reset_btn.setObjectName("secondaryBtn")
                reset_btn.clicked.connect(lambda: self._set_status("planned"))
                btn_layout.addWidget(reset_btn)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryBtn")
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _set_status(self, status: str):
        self.new_status = status
        self.accept()


# ═══════════════════════════════════════════════════════════════════════════
# Pace Calculator Dialog
# ═══════════════════════════════════════════════════════════════════════════

class PaceCalculatorDialog(QDialog):
    """Input distance + time → VDOT + all 5 pace zones."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pace Calculator")
        self.setMinimumSize(460, 520)
        self.setStyleSheet(DIALOG_STYLE)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("🧮  Pace Calculator")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #1A1A2E;")
        layout.addWidget(title)

        subtitle = QLabel("Enter a race result to calculate your VDOT and training paces")
        subtitle.setStyleSheet("color: #555; font-size: 13px; margin-bottom: 8px;")
        layout.addWidget(subtitle)

        # Input group
        input_group = QGroupBox("Race Result")
        input_form = QFormLayout(input_group)
        input_form.setSpacing(10)
        input_form.setContentsMargins(16, 24, 16, 16)

        self.dist_combo = QComboBox()
        self.dist_combo.addItems(["5K", "10K", "HM", "Marathon"])
        input_form.addRow("Distance:", self.dist_combo)

        time_layout = QHBoxLayout()
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(4)

        self.calc_hours = QSpinBox()
        self.calc_hours.setRange(0, 10)
        self.calc_hours.setSuffix(" h")
        time_layout.addWidget(self.calc_hours)

        self.calc_mins = QSpinBox()
        self.calc_mins.setRange(0, 59)
        self.calc_mins.setValue(25)
        self.calc_mins.setSuffix(" m")
        time_layout.addWidget(self.calc_mins)

        self.calc_secs = QSpinBox()
        self.calc_secs.setRange(0, 59)
        self.calc_secs.setSuffix(" s")
        time_layout.addWidget(self.calc_secs)
        time_layout.addStretch()

        input_form.addRow("Finish Time:", time_layout)
        layout.addWidget(input_group)

        calc_btn = QPushButton("⚡ Calculate")
        calc_btn.setObjectName("primaryBtn")
        calc_btn.clicked.connect(self._calculate)
        layout.addWidget(calc_btn)

        # Result area
        self.result_group = QGroupBox("Results")
        self.result_layout = QVBoxLayout(self.result_group)
        self.result_layout.setContentsMargins(16, 24, 16, 16)
        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("color: #1A1A2E;")
        self.result_layout.addWidget(self.result_label)
        self.result_group.hide()
        layout.addWidget(self.result_group)

        layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryBtn")
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)

    def _calculate(self):
        total_secs = (self.calc_hours.value() * 3600
                      + self.calc_mins.value() * 60
                      + self.calc_secs.value())
        if total_secs < 60:
            QMessageBox.warning(self, "Invalid", "Enter a valid race time.")
            return

        dist_key = self.dist_combo.currentText()
        dist_m = RACE_DISTANCES[dist_key]
        time_min = total_secs / 60.0

        vdot = calculate_vdot(dist_m, time_min)
        zones = vdot_to_pace_zones(vdot)

        # Race predictions
        predictions = []
        for rd_name, rd_m in RACE_DISTANCES.items():
            pred = vdot_to_race_prediction(vdot, rd_m)
            predictions.append(f"<b>{rd_name}:</b> {format_time(pred)}")

        zone_lines = []
        for z_name, z in zones.items():
            color = ZONE_COLORS.get(z_name, "#333")
            zone_lines.append(
                f'<span style="color:{color}; font-weight:600;">● {z_name}</span>: '
                f'{format_pace(z.min_pace_min_km)} – '
                f'{format_pace(z.max_pace_min_km)} min/km'
            )

        html = f"""
        <div style="font-size:13px; color: #1A1A2E;">
        <p><b>VDOT:</b> <span style="color:#6C63FF; font-size:20px; font-weight:bold;">
            {vdot:.1f}</span></p>
        <hr style="border-color:#E0E0E8;">
        <p><b>Race Predictions:</b></p>
        {'<br>'.join(predictions)}
        <hr style="border-color:#E0E0E8;">
        <p><b>Training Pace Zones:</b></p>
        {'<br>'.join(zone_lines)}
        </div>
        """
        self.result_label.setText(html)
        self.result_group.show()
