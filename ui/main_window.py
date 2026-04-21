"""
Main application window — sidebar navigation and view container.
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QIcon, QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame,
)

from db.database import get_database
from ui.dashboard import DashboardView
from ui.calendar_view import CalendarView
from ui.plan_builder import PlanBuilderView
from ui.dialogs import PaceCalculatorDialog, WelcomeDialog

# ═══════════════════════════════════════════════════════════════════════════
# Styles
# ═══════════════════════════════════════════════════════════════════════════

NAV_BUTTON_STYLE = """
QPushButton {
    text-align: left;
    padding: 12px 16px;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: #A0A0B0;
    font-size: 14px;
    font-weight: 500;
}
QPushButton:hover {
    background: #2A2A48;
    color: white;
}
QPushButton:checked {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #6C63FF, stop:1 #8B5CF6);
    color: white;
    font-weight: 600;
}
"""


class MainWindow(QMainWindow):
    """Main window holding the sidebar and the stacked main views."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Runna")
        self.setMinimumSize(1100, 800)
        
        self.current_plan_id: int | None = None

        self._build_sidebar()
        self._build_views()
        self._build_layout()

        # Connect signals
        self.plan_builder_view.plan_selected.connect(self._on_plan_selected)
        self.plan_builder_view.plan_deleted.connect(self._on_plan_deleted)
        self.dashboard_view.open_pace_calculator.connect(self._open_pace_calculator)

        self._check_first_run()

    def _check_first_run(self):
        """Check if DB is empty and show Welcome Wizard if so."""
        db = get_database()
        if not db.has_plans():
            welcome = WelcomeDialog(self)
            if welcome.exec() and welcome.generated_plan:
                # Save the generated plan from wizard
                plan_id = db.save_plan(welcome.generated_plan)
                self.plan_builder_view.refresh()
                self._on_plan_selected(plan_id)
        else:
            self._load_latest_plan()

    def _load_latest_plan(self):
        """Load the most recently created plan on startup."""
        db = get_database()
        plans = db.get_all_plans()
        if plans:
            self._on_plan_selected(plans[0]["id"])

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------
    def _build_sidebar(self):
        self.sidebar = QWidget()
        self.sidebar.setStyleSheet("background: #1E1E36;")
        self.sidebar.setFixedWidth(240)

        nav_layout = QVBoxLayout(self.sidebar)
        nav_layout.setContentsMargins(16, 24, 16, 24)
        nav_layout.setSpacing(8)

        # App Logo & Title
        title_layout = QHBoxLayout()
        logo = QLabel("🏃")
        logo.setStyleSheet("font-size: 28px; background: transparent; border: none;")
        title = QLabel("Runna")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title.setStyleSheet("color: white; background: transparent; border: none;")

        title_layout.addWidget(logo)
        title_layout.addWidget(title)
        title_layout.addStretch()

        nav_layout.addLayout(title_layout)
        nav_layout.addSpacing(32)

        # Nav Buttons
        self.nav_btns: list[QPushButton] = []

        self.btn_dashboard = QPushButton("📊  Dashboard")
        self.btn_plans = QPushButton("📝  Training Plans")
        self.btn_calendar = QPushButton("📅  Schedule")

        for btn in [self.btn_dashboard, self.btn_plans, self.btn_calendar]:
            btn.setCheckable(True)
            btn.setStyleSheet(NAV_BUTTON_STYLE)
            btn.clicked.connect(self._on_nav_clicked)
            self.nav_btns.append(btn)
            nav_layout.addWidget(btn)

        nav_layout.addStretch()

        # Tools separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #3A3A5A; margin: 16px 0;")
        nav_layout.addWidget(sep)

        # Pace Calculator Button
        self.btn_calc = QPushButton("🧮  Pace Calculator")
        self.btn_calc.setStyleSheet(NAV_BUTTON_STYLE)
        self.btn_calc.clicked.connect(self._open_pace_calculator)
        nav_layout.addWidget(self.btn_calc)

        nav_layout.addSpacing(16)

        # Active Plan Info card at bottom
        self.active_plan_card = QFrame()
        self.active_plan_card.setStyleSheet("""
            background: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            padding: 12px;
        """)
        ap_layout = QVBoxLayout(self.active_plan_card)
        ap_layout.setContentsMargins(12, 12, 12, 12)
        ap_layout.setSpacing(4)

        ap_lbl = QLabel("ACTIVE PLAN")
        ap_lbl.setStyleSheet("color: #888; font-size: 10px; font-weight: bold;")
        ap_layout.addWidget(ap_lbl)

        self.active_plan_name = QLabel("No plan selected")
        self.active_plan_name.setStyleSheet("color: white; font-size: 13px; font-weight: 600;")
        self.active_plan_name.setWordWrap(True)
        ap_layout.addWidget(self.active_plan_name)

        nav_layout.addWidget(self.active_plan_card)

        # Version label
        version = QLabel("v1.0.0")
        version.setStyleSheet("color: #5A5A7A; font-size: 11px;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_layout.addWidget(version)

    def _build_views(self):
        self.view_stack = QStackedWidget()
        self.view_stack.setStyleSheet("background: #F5F5FA;")

        self.dashboard_view = DashboardView(self)
        self.plan_builder_view = PlanBuilderView(self)
        self.calendar_view = CalendarView(self)

        self.view_stack.addWidget(self.dashboard_view)    # Index 0
        self.view_stack.addWidget(self.plan_builder_view) # Index 1
        self.view_stack.addWidget(self.calendar_view)     # Index 2

    def _build_layout(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.view_stack)

        self.setCentralWidget(main_widget)
        
        # Select dashboard by default
        self.btn_dashboard.setChecked(True)
        self.view_stack.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # Navigation & Actions
    # ------------------------------------------------------------------
    def _on_nav_clicked(self):
        sender = self.sender()
        if not isinstance(sender, QPushButton):
            return

        # Uncheck others
        for btn in self.nav_btns:
            if btn != sender:
                btn.setChecked(False)
        sender.setChecked(True)

        if sender == self.btn_dashboard:
            self.view_stack.setCurrentIndex(0)
            self.dashboard_view._refresh() # re-render charts if needed
        elif sender == self.btn_plans:
            self.view_stack.setCurrentIndex(1)
            # Re-select current plan in list if we have one
            if self.current_plan_id:
                for i in range(self.plan_builder_view.plan_list.count()):
                    item = self.plan_builder_view.plan_list.item(i)
                    if item.data(Qt.ItemDataRole.UserRole) == self.current_plan_id:
                        self.plan_builder_view.plan_list.setCurrentRow(i)
                        break
        elif sender == self.btn_calendar:
            self.view_stack.setCurrentIndex(2)
            self.calendar_view._refresh()

    def _open_pace_calculator(self):
        dlg = PaceCalculatorDialog(self)
        dlg.exec()

    def _on_plan_selected(self, plan_id: int):
        self.current_plan_id = plan_id
        db = get_database()
        plan = db.get_plan_by_id(plan_id)
        if plan:
            self.active_plan_name.setText(plan.name)
            self.dashboard_view.set_plan(plan)
            self.calendar_view.set_plan(plan)

    def _on_plan_deleted(self):
        """Handle case when active plan is deleted from planner view."""
        self.current_plan_id = None
        self.active_plan_name.setText("No plan selected")
        self._load_latest_plan() # load another if exists
        
    def closeEvent(self, event):
        """Cleanup DB connection on exit."""
        db = get_database()
        db.close()
        super().closeEvent(event)
