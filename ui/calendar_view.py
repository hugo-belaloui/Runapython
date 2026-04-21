"""
Calendar & Schedule view — monthly calendar grid + week list view,
color-coded sessions, click-to-view details, and status toggling.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QGridLayout, QScrollArea, QStackedWidget,
    QSizePolicy,
)

from core.models import FullPlan, Session
from db.database import get_database
from ui.dialogs import SessionDetailDialog
from ui.styles import (
    CARD_STYLE, SESSION_COLORS, SESSION_BG_COLORS, format_pace,
)


# ═══════════════════════════════════════════════════════════════════════════
# Calendar Day Cell
# ═══════════════════════════════════════════════════════════════════════════

class DayCell(QFrame):
    """A single day cell in the calendar grid."""

    clicked = pyqtSignal(object)  # emits the Session or None

    def __init__(self, day_date: date | None = None, session: Session | None = None,
                 is_current_month: bool = True, parent=None):
        super().__init__(parent)
        self.day_date = day_date
        self.session = session
        self.is_current_month = is_current_month
        self.setCursor(Qt.CursorShape.PointingHandCursor if session else
                       Qt.CursorShape.ArrowCursor)
        self.setMinimumSize(100, 90)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._build_ui()

    def _build_ui(self):
        if self.day_date is None:
            self.setStyleSheet("background: transparent; border: none;")
            return

        session_type = self.session.session_type if self.session else "Rest"
        bg_color = SESSION_BG_COLORS.get(session_type, "#FAFAFA")
        border_color = SESSION_COLORS.get(session_type, "#E0E0E0")

        # Convert hex to rgba for transparency if not current month
        # Removing CSS opacity property which does not work in Qt
        if not self.is_current_month:
            # Simple approximation: lighten the border and background colors
            bg_color = "#F8F8FA"  # neutral out-of-month background
            border_color = "#E0E0E8"

        is_today = self.day_date == date.today()
        today_border = f"border: 2px solid #6C63FF;" if is_today else f"border: 1px solid {border_color};"

        self.setStyleSheet(f"""
            QFrame {{
                background: {bg_color};
                {today_border}
                border-radius: 8px;
            }}
            QFrame:hover {{
                border-color: #6C63FF;
                border-width: 2px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        # Day number
        day_num = QLabel(str(self.day_date.day))
        day_color = "#6C63FF" if is_today else ("#1A1A2E" if self.is_current_month else "#A0A0B0")
        day_weight = "bold" if is_today else "600"
        day_num.setStyleSheet(f"color: {day_color}; font-size: 13px; "
                              f"font-weight: {day_weight}; border: none; background: transparent;")
        layout.addWidget(day_num)

        if self.session and self.session.session_type != "Rest":
            # Session type badge
            color = SESSION_COLORS.get(self.session.session_type, "#555")
            type_label = QLabel(f"● {self.session.session_type}")
            # If not current month, dim the text color
            if not self.is_current_month:
                color = "#999"

            type_label.setStyleSheet(f"color: {color}; font-size: 11px; "
                                     f"font-weight: bold; border: none; background: transparent;")
            layout.addWidget(type_label)

            # Distance
            if self.session.distance_km > 0:
                dist_label = QLabel(f"{self.session.distance_km:.1f} km")
                dist_color = "#444" if self.is_current_month else "#AAA"
                dist_label.setStyleSheet(f"color: {dist_color}; font-size: 10px; border: none; background: transparent;")
                layout.addWidget(dist_label)

            # Status indicator
            if self.session.status == "completed":
                status_lbl = QLabel("✅")
                status_lbl.setStyleSheet("font-size: 12px; border: none; background: transparent;")
                layout.addWidget(status_lbl)
            elif self.session.status == "skipped":
                status_lbl = QLabel("⏭")
                status_lbl.setStyleSheet("font-size: 12px; border: none; background: transparent;")
                layout.addWidget(status_lbl)

        layout.addStretch()

    def mousePressEvent(self, event):
        if self.session:
            self.clicked.emit(self.session)
        super().mousePressEvent(event)


# ═══════════════════════════════════════════════════════════════════════════
# Week Row (for list view)
# ═══════════════════════════════════════════════════════════════════════════

class WeekRow(QFrame):
    """A single week row in the list view."""

    session_clicked = pyqtSignal(object)

    def __init__(self, week_start: date, sessions: list[Session], phase: str = "Base", parent=None):
        super().__init__(parent)
        self.week_start = week_start
        self.sessions = sessions
        self.phase = phase
        self.setStyleSheet(CARD_STYLE + " margin-bottom: 8px;")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Week header
        week_end = self.week_start + timedelta(days=6)
        
        header_layout = QHBoxLayout()
        header = QLabel(f"<b>{self.week_start.strftime('%b %d')} – "
                        f"{week_end.strftime('%b %d, %Y')}</b>")
        header.setStyleSheet("color: #1A1A2E; font-size: 14px; border: none;")
        header_layout.addWidget(header)
        
        # Add phase label
        from ui.styles import PHASE_COLORS
        pc = PHASE_COLORS.get(self.phase, "#6C63FF")
        phase_lbl = QLabel(self.phase)
        phase_lbl.setStyleSheet(f"color: {pc}; font-size: 12px; font-weight: bold; border: none;")
        header_layout.addWidget(phase_lbl)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Total km
        total_km = sum(s.distance_km for s in self.sessions if s.session_type != "Rest")
        sub = QLabel(f"Total: {total_km:.1f} km")
        sub.setStyleSheet("color: #666; font-size: 12px; border: none;")
        layout.addWidget(sub)

        # Session list
        for session in self.sessions:
            if session.session_type == "Rest":
                continue

            row = QFrame()
            row.setCursor(Qt.CursorShape.PointingHandCursor)
            color = SESSION_COLORS.get(session.session_type, "#555")
            bg = SESSION_BG_COLORS.get(session.session_type, "#F9F9F9")
            
            # Use rgba for slight border transparency
            # Can't easily use variables internally in stylesheet without f-strings
            row.setStyleSheet(f"""
                QFrame {{
                    background: {bg};
                    border: 1px solid #E0E0E8;
                    border-left: 4px solid {color};
                    border-radius: 6px;
                    padding: 8px 12px;
                }}
                QFrame:hover {{
                    border-color: {color};
                }}
            """)

            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 6, 8, 6)
            row_layout.setSpacing(12)

            day_lbl = QLabel(session.date.strftime("%a"))
            day_lbl.setStyleSheet(f"color: #444; font-size: 12px; font-weight: 600; "
                                  f"min-width: 36px; border: none;")
            row_layout.addWidget(day_lbl)

            type_lbl = QLabel(f'<span style="color:{color}; font-weight:bold;">'
                              f'● {session.session_type}</span>')
            type_lbl.setStyleSheet("font-size: 13px; border: none;")
            row_layout.addWidget(type_lbl)

            dist_lbl = QLabel(f"{session.distance_km:.1f} km")
            dist_lbl.setStyleSheet("color: #1A1A2E; font-size: 13px; border: none;")
            row_layout.addWidget(dist_lbl)

            if session.pace_target_min_km:
                pace_str = format_pace(session.pace_target_min_km)
            else:
                pace_str = "—"
            
            pace_lbl = QLabel(f"{pace_str} /km")
            pace_lbl.setStyleSheet("color: #555; font-size: 12px; border: none;")
            row_layout.addWidget(pace_lbl)

            row_layout.addStretch()

            # Status
            status_icons = {"completed": "✅", "skipped": "⏭", "planned": "○"}
            status_lbl = QLabel(status_icons.get(session.status, "○"))
            status_lbl.setStyleSheet("font-size: 14px; border: none; color: #1A1A2E;")
            row_layout.addWidget(status_lbl)

            # Make row clickable
            row.mousePressEvent = lambda e, s=session: self.session_clicked.emit(s)

            layout.addWidget(row)


# ═══════════════════════════════════════════════════════════════════════════
# Calendar View Widget
# ═══════════════════════════════════════════════════════════════════════════

class CalendarView(QWidget):
    """Monthly calendar grid + week list view with navigation and session clicks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_plan: FullPlan | None = None
        self.sessions_cache: list[tuple[Session, str]] = []  # Stores (Session, phase) pairs based on DB update
        self.current_year = date.today().year
        self.current_month = date.today().month
        self.current_view = "calendar"  # "calendar" or "list"
        self.calendar_grid: QWidget | None = None # Keep reference for cleanup
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # ── Header: title + nav + view toggle ──
        header = QHBoxLayout()
        header.setSpacing(12)

        title = QLabel("Schedule")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setStyleSheet("color: #1A1A2E;")
        header.addWidget(title)

        header.addStretch()

        # View toggle
        self.cal_toggle = QPushButton("📅 Calendar")
        self.cal_toggle.setStyleSheet(self._toggle_style(True))
        self.cal_toggle.clicked.connect(lambda: self._set_view("calendar"))
        header.addWidget(self.cal_toggle)

        self.list_toggle = QPushButton("📋 Week List")
        self.list_toggle.setStyleSheet(self._toggle_style(False))
        self.list_toggle.clicked.connect(lambda: self._set_view("list"))
        header.addWidget(self.list_toggle)

        main_layout.addLayout(header)

        # ── Month navigation ──
        nav = QHBoxLayout()
        nav.setSpacing(8)

        prev_btn = QPushButton("◀")
        prev_btn.setFixedSize(36, 36)
        prev_btn.setStyleSheet("""
            QPushButton {
                background: white; border: 1px solid #E0E0E8;
                border-radius: 8px; font-size: 14px; color: #1A1A2E;
            }
            QPushButton:hover { background: #F0EEFF; border-color: #6C63FF; }
        """)
        prev_btn.clicked.connect(self._prev_month)
        nav.addWidget(prev_btn)

        self.month_label = QLabel()
        self.month_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.month_label.setStyleSheet("color: #1A1A2E;")
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.month_label.setMinimumWidth(200)
        nav.addWidget(self.month_label)

        next_btn = QPushButton("▶")
        next_btn.setFixedSize(36, 36)
        next_btn.setStyleSheet("""
            QPushButton {
                background: white; border: 1px solid #E0E0E8;
                border-radius: 8px; font-size: 14px; color: #1A1A2E;
            }
            QPushButton:hover { background: #F0EEFF; border-color: #6C63FF; }
        """)
        next_btn.clicked.connect(self._next_month)
        nav.addWidget(next_btn)

        today_btn = QPushButton("Today")
        today_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #6C63FF, stop:1 #8B5CF6);
                color: white; border: none; border-radius: 6px;
                padding: 6px 16px; font-size: 13px; font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #5B52E0, stop:1 #7C4FE0);
            }
        """)
        today_btn.clicked.connect(self._go_today)
        nav.addWidget(today_btn)

        nav.addStretch()

        # Legend
        for stype, scolor in SESSION_COLORS.items():
            if stype == "Rest": continue
            dot = QLabel(f'<span style="color:{scolor};">●</span> {stype}')
            dot.setStyleSheet("font-size: 11px; color: #555;")
            nav.addWidget(dot)

        main_layout.addLayout(nav)

        # ── Stacked widget for calendar/list views ──
        self.view_stack = QStackedWidget()

        # Calendar view
        self.calendar_scroll = QScrollArea()
        self.calendar_scroll.setWidgetResizable(True)
        self.calendar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.calendar_scroll.setStyleSheet("QScrollArea { background: #F5F5FA; border: none; }")

        self.calendar_container = QWidget()
        self.calendar_grid_layout = QVBoxLayout(self.calendar_container)
        self.calendar_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.calendar_scroll.setWidget(self.calendar_container)
        self.view_stack.addWidget(self.calendar_scroll)

        # List view
        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.list_scroll.setStyleSheet("QScrollArea { background: #F5F5FA; border: none; }")

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_scroll.setWidget(self.list_container)
        self.view_stack.addWidget(self.list_scroll)

        main_layout.addWidget(self.view_stack)

        self._update_month_label()

    def _toggle_style(self, active: bool) -> str:
        if active:
            return """
                QPushButton {
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 #6C63FF, stop:1 #8B5CF6);
                    color: white; border: none; border-radius: 6px;
                    padding: 6px 14px; font-size: 12px; font-weight: 600;
                }
            """
        return """
            QPushButton {
                background: white; color: #444;
                border: 1px solid #E0E0E8; border-radius: 6px;
                padding: 6px 14px; font-size: 12px; font-weight: 600;
            }
            QPushButton:hover { background: #F0EEFF; border-color: #6C63FF; }
        """

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def _prev_month(self):
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self._refresh()

    def _next_month(self):
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self._refresh()

    def _go_today(self):
        today = date.today()
        self.current_year = today.year
        self.current_month = today.month
        self._refresh()

    def _set_view(self, view: str):
        self.current_view = view
        self.cal_toggle.setStyleSheet(self._toggle_style(view == "calendar"))
        self.list_toggle.setStyleSheet(self._toggle_style(view == "list"))
        self.view_stack.setCurrentIndex(0 if view == "calendar" else 1)
        self._refresh()

    def _update_month_label(self):
        month_name = calendar.month_name[self.current_month]
        self.month_label.setText(f"{month_name} {self.current_year}")

    # ------------------------------------------------------------------
    # Plan loading
    # ------------------------------------------------------------------
    def set_plan(self, plan: FullPlan):
        self.current_plan = plan
        db = get_database()
        
        # We need both session and phase to render list properly 
        # So reconstruct the (Session, Phase) view cache from the FullPlan object
        self.sessions_cache = []
        for week in plan.weeks:
            for session in week.sessions:
                self.sessions_cache.append((session, week.phase))
        
        self._refresh()

    def _get_session_for_date(self, d: date) -> Session | None:
        for s, _ in self.sessions_cache:
            if s.date == d:
                return s
        return None

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------
    def _refresh(self):
        self._update_month_label()
        if self.current_view == "calendar":
            self._build_calendar_grid()
        else:
            self._build_week_list()

    def _build_calendar_grid(self):
        # Clear existing safely to prevent memory leak
        if self.calendar_grid is not None:
             self.calendar_grid_layout.removeWidget(self.calendar_grid)
             self.calendar_grid.deleteLater()
             self.calendar_grid = None

        grid = QGridLayout()
        grid.setSpacing(4)

        # Day headers
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for col, name in enumerate(day_names):
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #555; font-size: 12px; font-weight: 600; "
                              "padding: 6px;")
            grid.addWidget(lbl, 0, col)

        # Calendar days
        cal = calendar.Calendar(firstweekday=0)  # Monday start
        month_days = cal.monthdatescalendar(self.current_year, self.current_month)

        for row_idx, week in enumerate(month_days, start=1):
            for col_idx, day in enumerate(week):
                is_current = day.month == self.current_month
                session = self._get_session_for_date(day)
                cell = DayCell(day, session, is_current)
                cell.clicked.connect(self._on_session_clicked)
                grid.addWidget(cell, row_idx, col_idx)

        self.calendar_grid = QWidget()
        self.calendar_grid.setLayout(grid)
        self.calendar_grid_layout.addWidget(self.calendar_grid)
        self.calendar_grid_layout.addStretch()

    def _build_week_list(self):
        self._clear_layout(self.list_layout)

        # Get first and last day of month
        first_day = date(self.current_year, self.current_month, 1)
        if self.current_month == 12:
            last_day = date(self.current_year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(self.current_year, self.current_month + 1, 1) - timedelta(days=1)

        # Iterate weeks
        week_start = first_day - timedelta(days=first_day.weekday())

        while week_start <= last_day:
            week_end = week_start + timedelta(days=6)
            
            # Find sessions for this week
            week_sessions = []
            phase_for_week = "Base"
            
            for s, phase in self.sessions_cache:
                if week_start <= s.date <= week_end:
                    week_sessions.append(s)
                    phase_for_week = phase

            if week_sessions:
                row = WeekRow(week_start, week_sessions, phase=phase_for_week)
                row.session_clicked.connect(self._on_session_clicked)
                self.list_layout.addWidget(row)

            week_start += timedelta(days=7)

        self.list_layout.addStretch()
        
    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    # ------------------------------------------------------------------
    # Session interaction
    # ------------------------------------------------------------------
    def _on_session_clicked(self, session: Session):
        if session is None or session.session_type == "Rest":
            return

        dlg = SessionDetailDialog(session, self)
        if dlg.exec() and dlg.new_status:
            db = get_database()
            if session.id:
                db.update_session_status(session.id, dlg.new_status)
                # Refresh cache via full plan reload from DB internally to main_window
                # so other views update too
                
                # To be clean, emit an event upwards, but here we can just reload the full plan
                # which keeps the pattern
                if self.current_plan:
                    updated_plan = db.get_plan_by_id(self.current_plan.id)
                    if updated_plan:
                        self.set_plan(updated_plan)
