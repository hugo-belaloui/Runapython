"""
Plan Builder view — list saved plans, create/duplicate/delete, view plan details.
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QListWidget, QListWidgetItem, QScrollArea,
    QSplitter, QMessageBox, QGridLayout, QSizePolicy,
)

from core.models import FullPlan, RACE_DISTANCES
from core.training_engine import vdot_to_race_prediction
from db.database import get_database
from ui.dialogs import PlanGenerationDialog
from ui.styles import (
    CARD_STYLE, ZONE_COLORS, PHASE_COLORS, format_pace, format_time,
)

# ═══════════════════════════════════════════════════════════════════════════
# Styles
# ═══════════════════════════════════════════════════════════════════════════

SIDEBAR_STYLE = """
QListWidget {
    background: #1E1E36;
    border: none;
    border-radius: 0;
    padding: 8px;
    font-size: 13px;
}
QListWidget::item {
    color: #C8C8D8;
    padding: 12px 14px;
    border-radius: 8px;
    margin-bottom: 4px;
}
QListWidget::item:selected {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #6C63FF, stop:1 #8B5CF6);
    color: white;
}
QListWidget::item:hover:!selected {
    background: #2A2A48;
}
"""


class PlanBuilderView(QWidget):
    """Plan management: list, create, duplicate, delete, view details."""

    plan_selected = pyqtSignal(int)  # emits plan_id when a plan is selected
    plan_deleted = pyqtSignal()  # emits when active plan is deleted

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_plan: FullPlan | None = None
        self._build_ui()
        self._refresh_plan_list()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left panel: plan list ──
        left_panel = QWidget()
        left_panel.setStyleSheet("background: #1A1A2E;")
        left_panel.setMinimumWidth(260)
        left_panel.setMaximumWidth(340)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet("background: #1A1A2E; padding: 16px;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 16, 16, 12)

        plans_title = QLabel("Training Plans")
        plans_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        plans_title.setStyleSheet("color: white;")
        header_layout.addWidget(plans_title)

        # New plan button
        new_btn = QPushButton("＋  New Plan")
        new_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #6C63FF, stop:1 #8B5CF6);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 14px;
                font-weight: 600;
                margin-top: 8px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #5B52E0, stop:1 #7C4FE0);
            }
        """)
        new_btn.clicked.connect(self._on_new_plan)
        header_layout.addWidget(new_btn)

        left_layout.addWidget(header)

        # Plan list
        self.plan_list = QListWidget()
        self.plan_list.setStyleSheet(SIDEBAR_STYLE)
        self.plan_list.currentRowChanged.connect(self._on_plan_selected)
        left_layout.addWidget(self.plan_list)

        # Action buttons
        action_bar = QWidget()
        action_bar.setStyleSheet("background: #1A1A2E;")
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(12, 8, 12, 12)
        action_layout.setSpacing(8)

        dup_btn = QPushButton("📋 Duplicate")
        dup_btn.setStyleSheet("""
            QPushButton {
                background: #2A2A48;
                color: #C8C8D8;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
            }
            QPushButton:hover { background: #3A3A58; }
        """)
        dup_btn.clicked.connect(self._on_duplicate)
        action_layout.addWidget(dup_btn)

        del_btn = QPushButton("🗑 Delete")
        del_btn.setStyleSheet("""
            QPushButton {
                background: #2A2A48;
                color: #EF4444;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
            }
            QPushButton:hover { background: #3A3A58; }
        """)
        del_btn.clicked.connect(self._on_delete)
        action_layout.addWidget(del_btn)

        left_layout.addWidget(action_bar)

        splitter.addWidget(left_panel)

        # ── Right panel: plan details ──
        right_panel = QWidget()
        right_panel.setStyleSheet("background: #F5F5FA;")

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setStyleSheet("QScrollArea { background: #F5F5FA; border: none; }")

        self.detail_container = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_container)
        self.detail_layout.setContentsMargins(24, 24, 24, 24)
        self.detail_layout.setSpacing(16)

        # Empty state
        self._show_empty_state()

        right_scroll.setWidget(self.detail_container)

        right_wrapper = QVBoxLayout(right_panel)
        right_wrapper.setContentsMargins(0, 0, 0, 0)
        right_wrapper.addWidget(right_scroll)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 700])

        layout.addWidget(splitter)
        
    def _show_empty_state(self):
        self._clear_detail_layout()
        empty_label = QLabel("Select a plan or create a new one to get started")
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_label.setStyleSheet("color: #777; font-size: 16px; padding: 60px;")
        self.detail_layout.addWidget(empty_label)
        self.detail_layout.addStretch()

    # ------------------------------------------------------------------
    # Plan list management
    # ------------------------------------------------------------------
    def _refresh_plan_list(self):
        self.plan_list.clear() # disconnects signals implicitly
        db = get_database()
        plans = db.get_all_plans()

        for p in plans:
            race_date = date.fromisoformat(p["race_date"])
            days_until = (race_date - date.today()).days
            label = f"{p['name']}\n{p['race_distance']}  •  VDOT {p['vdot']:.0f}"
            if days_until > 0:
                label += f"  •  {days_until}d to race"
            else:
                label += "  •  Race completed"

            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, p["id"])
            item.setSizeHint(QSize(260, 56))
            self.plan_list.addItem(item)

    def _on_plan_selected(self, row):
        if row < 0:
            return
        item = self.plan_list.item(row)
        if item is None:
            return
        plan_id = item.data(Qt.ItemDataRole.UserRole)
        db = get_database()
        plan = db.get_plan_by_id(plan_id)
        if plan:
            self.current_plan = plan
            self._show_plan_details(plan)
            self.plan_selected.emit(plan_id)

    def _show_plan_details(self, plan: FullPlan):
        """Populate the right panel with plan details."""
        self._clear_detail_layout()

        # Title
        title = QLabel(plan.name)
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setStyleSheet("color: #1A1A2E;")
        self.detail_layout.addWidget(title)

        # Info cards row
        info_layout = QGridLayout()
        info_layout.setSpacing(12)

        info_items = [
            ("Race", plan.race_distance, "🏆"),
            ("Race Date", plan.race_date.strftime("%b %d, %Y"), "📅"),
            ("VDOT", f"{plan.vdot:.1f}", "💪"),
            ("Weeks", str(plan.total_weeks), "📊"),
            ("Days/Week", str(plan.days_per_week), "🗓"),
            ("Total Sessions", str(plan.total_sessions), "🏃"),
        ]

        for i, (label, value, icon) in enumerate(info_items):
            card = QFrame()
            card.setStyleSheet(CARD_STYLE)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 12, 16, 12)
            card_layout.setSpacing(2)

            icon_label = QLabel(f"{icon} {label}")
            icon_label.setStyleSheet("color: #666; font-size: 11px; font-weight: 600; "
                                     "text-transform: uppercase; border: none;")
            card_layout.addWidget(icon_label)

            val_label = QLabel(value)
            val_label.setStyleSheet("color: #1A1A2E; font-size: 20px; "
                                    "font-weight: bold; border: none;")
            card_layout.addWidget(val_label)

            info_layout.addWidget(card, i // 3, i % 3)

        self.detail_layout.addLayout(info_layout)

        # Race prediction
        race_dist_m = RACE_DISTANCES.get(plan.race_distance, 42195)
        pred_time = vdot_to_race_prediction(plan.vdot, race_dist_m)
        pred_card = QFrame()
        pred_card.setStyleSheet("""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #6C63FF, stop:1 #8B5CF6);
            border-radius: 12px;
            padding: 20px;
        """)
        pred_layout = QVBoxLayout(pred_card)
        pred_layout.setContentsMargins(20, 16, 20, 16)

        pred_title = QLabel("🎯  Race Prediction")
        pred_title.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 13px; "
                                 "font-weight: 600; border: none;")
        pred_layout.addWidget(pred_title)

        pred_value = QLabel(format_time(pred_time))
        pred_value.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        pred_value.setStyleSheet("color: white; border: none;")
        pred_layout.addWidget(pred_value)

        all_preds = []
        for rd_name, rd_m in RACE_DISTANCES.items():
            t = vdot_to_race_prediction(plan.vdot, rd_m)
            all_preds.append(f"{rd_name}: {format_time(t)}")
        pred_sub = QLabel("  |  ".join(all_preds))
        pred_sub.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 12px; border: none;")
        pred_sub.setWordWrap(True)
        pred_layout.addWidget(pred_sub)

        self.detail_layout.addWidget(pred_card)

        # Pace zones
        zones_card = QFrame()
        zones_card.setStyleSheet(CARD_STYLE)
        zones_layout = QVBoxLayout(zones_card)
        zones_layout.setContentsMargins(20, 16, 20, 16)

        zones_title = QLabel("🎯  Training Pace Zones")
        zones_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        zones_title.setStyleSheet("color: #1A1A2E; border: none;")
        zones_layout.addWidget(zones_title)

        zones_grid = QGridLayout()
        zones_grid.setSpacing(8)
        headers = ["Zone", "Fast End", "Slow End", "Purpose"]
        for col, h in enumerate(headers):
            lbl = QLabel(f"<b>{h}</b>")
            lbl.setStyleSheet("color: #666; font-size: 11px; border: none; padding: 4px;")
            zones_grid.addWidget(lbl, 0, col)

        for row, zone in enumerate(plan.pace_zones, start=1):
            color = ZONE_COLORS.get(zone.zone_name, "#333")
            name_lbl = QLabel(f'<span style="color:{color}; font-weight:bold;">'
                              f'● {zone.zone_name}</span>')
            name_lbl.setStyleSheet("font-size: 13px; border: none; padding: 4px;")
            zones_grid.addWidget(name_lbl, row, 0)

            fast = QLabel(f"{format_pace(zone.min_pace_min_km)} /km")
            fast.setStyleSheet("color: #1A1A2E; font-size: 13px; border: none; padding: 4px;")
            zones_grid.addWidget(fast, row, 1)

            slow = QLabel(f"{format_pace(zone.max_pace_min_km)} /km")
            slow.setStyleSheet("color: #1A1A2E; font-size: 13px; border: none; padding: 4px;")
            zones_grid.addWidget(slow, row, 2)

            desc = QLabel(f'<span style="color:#777;">{zone.description}</span>')
            desc.setStyleSheet("font-size: 12px; border: none; padding: 4px;")
            zones_grid.addWidget(desc, row, 3)

        zones_layout.addLayout(zones_grid)
        self.detail_layout.addWidget(zones_card)

        # Week overview
        week_card = QFrame()
        week_card.setStyleSheet(CARD_STYLE)
        week_layout = QVBoxLayout(week_card)
        week_layout.setContentsMargins(20, 16, 20, 16)

        week_title = QLabel("📋  Weekly Overview")
        week_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        week_title.setStyleSheet("color: #1A1A2E; border: none;")
        week_layout.addWidget(week_title)

        week_grid = QGridLayout()
        week_grid.setSpacing(6)
        headers = ["Week", "Dates", "Phase", "Volume"]
        for col, h in enumerate(headers):
            lbl = QLabel(f"<b>{h}</b>")
            lbl.setStyleSheet("color: #666; font-size: 11px; border: none; padding: 4px;")
            week_grid.addWidget(lbl, 0, col)

        for row, w in enumerate(plan.weeks, start=1):
            wk = QLabel(f"W{w.week_number}")
            wk.setStyleSheet("color: #1A1A2E; font-size: 12px; border: none; padding: 3px 6px; "
                             "font-weight: 600;")
            week_grid.addWidget(wk, row, 0)

            dates = QLabel(f"{w.week_start_date.strftime('%b %d')} – "
                           f"{w.week_end_date.strftime('%b %d')}")
            dates.setStyleSheet("font-size: 12px; border: none; padding: 3px 6px; "
                                "color: #555;")
            week_grid.addWidget(dates, row, 1)

            pc = PHASE_COLORS.get(w.phase, "#333")
            phase = QLabel(f'<span style="color:{pc}; font-weight:600;">{w.phase}</span>')
            phase.setStyleSheet("font-size: 12px; border: none; padding: 3px 6px;")
            week_grid.addWidget(phase, row, 2)

            vol = QLabel(f"{w.target_weekly_km:.1f} km")
            vol.setStyleSheet("color: #1A1A2E; font-size: 12px; border: none; padding: 3px 6px; "
                              "font-weight: 600;")
            week_grid.addWidget(vol, row, 3)

        week_layout.addLayout(week_grid)
        self.detail_layout.addWidget(week_card)

        self.detail_layout.addStretch()

    def _clear_detail_layout(self):
        self._clear_layout(self.detail_layout)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_new_plan(self):
        dlg = PlanGenerationDialog(self)
        if dlg.exec() and dlg.generated_plan:
            db = get_database()
            plan_id = db.save_plan(dlg.generated_plan)
            self._refresh_plan_list()
            # Select the new plan
            for i in range(self.plan_list.count()):
                item = self.plan_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == plan_id:
                    self.plan_list.setCurrentRow(i)
                    break
            self.plan_selected.emit(plan_id)

    def _on_duplicate(self):
        if not self.current_plan or not self.current_plan.id:
            QMessageBox.information(self, "No Plan", "Select a plan to duplicate.")
            return
        db = get_database()
        new_id = db.duplicate_plan(self.current_plan.id)
        if new_id:
            self._refresh_plan_list()
            # Select the duplicated plan
            for i in range(self.plan_list.count()):
                item = self.plan_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == new_id:
                    self.plan_list.setCurrentRow(i)
                    break
            self.plan_selected.emit(new_id)

    def _on_delete(self):
        if not self.current_plan or not self.current_plan.id:
            QMessageBox.information(self, "No Plan", "Select a plan to delete.")
            return
        reply = QMessageBox.question(
            self, "Delete Plan",
            f"Are you sure you want to delete '{self.current_plan.name}'?\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            db = get_database()
            db.delete_plan(self.current_plan.id)
            self.current_plan = None
            self._refresh_plan_list()
            self._show_empty_state()
            self.plan_deleted.emit() # Notify parent so it unloads

    def refresh(self):
        """Public refresh method."""
        self._refresh_plan_list()
