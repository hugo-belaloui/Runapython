"""
Dashboard view — summary cards, weekly km chart, session distribution,
pace zones reference, and date range filters.
"""

from __future__ import annotations

from datetime import date, timedelta

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QPen, QLinearGradient
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGridLayout, QComboBox, QPushButton, QScrollArea, QSizePolicy,
)

import pyqtgraph as pg

from core.models import FullPlan, PaceZone, Session
from db.database import get_database
from ui.styles import (
    CARD_STYLE, SESSION_COLORS, ZONE_COLORS,
    format_pace,
)
from ui.dialogs import PaceCalculatorDialog


class SummaryCard(QFrame):
    """A single stat summary card."""

    def __init__(self, title: str, value: str, subtitle: str = "",
                 accent_color: str = "#6C63FF", parent=None):
        super().__init__(parent)
        self.setStyleSheet(CARD_STYLE)
        self.setMinimumHeight(110)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #666; font-size: 12px; font-weight: 600; "
                                  "text-transform: uppercase; border: none;")
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: {accent_color}; font-size: 28px; "
                                  f"font-weight: bold; border: none;")
        self.value_label = value_label
        layout.addWidget(value_label)

        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setStyleSheet("color: #777; font-size: 11px; border: none;")
            layout.addWidget(sub_label)

        layout.addStretch()

    def update_value(self, value: str):
        self.value_label.setText(value)


class DashboardView(QWidget):
    """Main dashboard with summary cards, charts, pace zones, and filters."""

    open_pace_calculator = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_plan: FullPlan | None = None
        self.filter_range = "all"  # "4w", "3m", "all"
        self._build_ui()

    def _build_ui(self):
        # Scroll wrapper
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: #F5F5FA; border: none; }")

        container = QWidget()
        self.main_layout = QVBoxLayout(container)
        self.main_layout.setContentsMargins(24, 24, 24, 24)
        self.main_layout.setSpacing(20)

        # ── Header row: title + filters ──
        header = QHBoxLayout()
        title = QLabel("Dashboard")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setStyleSheet("color: #1A1A2E;")
        header.addWidget(title)

        header.addStretch()

        # Date range filter
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Last 4 Weeks", "Last 3 Months", "All Time"])
        self.filter_combo.setCurrentIndex(2)
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        self.filter_combo.setStyleSheet("""
            QComboBox {
                padding: 6px 12px;
                border: 1px solid #D0D0D8;
                border-radius: 6px;
                background: white;
                color: #1A1A2E;
                font-size: 13px;
                min-width: 140px;
            }
            QComboBox QAbstractItemView {
                background: white;
                color: #1A1A2E;
                selection-background-color: #6C63FF;
                selection-color: white;
            }
        """)
        header.addWidget(self.filter_combo)

        # Pace calculator button
        calc_btn = QPushButton("🧮 Pace Calculator")
        calc_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #6C63FF, stop:1 #8B5CF6);
                color: white;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #5B52E0, stop:1 #7C4FE0);
            }
        """)
        calc_btn.clicked.connect(self._open_pace_calc)
        header.addWidget(calc_btn)

        self.main_layout.addLayout(header)

        # ── Summary cards row ──
        cards_layout = QGridLayout()
        cards_layout.setSpacing(16)

        self.card_weekly_km = SummaryCard("Weekly KM", "—", "This week", "#6C63FF")
        self.card_avg_pace = SummaryCard("Avg Pace", "—", "min/km", "#22C55E")
        self.card_sessions = SummaryCard("Sessions Done", "—", "vs planned", "#F59E0B")
        self.card_longest = SummaryCard("Longest Run", "—", "km", "#A855F7")

        cards_layout.addWidget(self.card_weekly_km, 0, 0)
        cards_layout.addWidget(self.card_avg_pace, 0, 1)
        cards_layout.addWidget(self.card_sessions, 0, 2)
        cards_layout.addWidget(self.card_longest, 0, 3)

        self.main_layout.addLayout(cards_layout)

        # ── Charts row ──
        charts_layout = QHBoxLayout()
        charts_layout.setSpacing(16)

        # Weekly km line chart
        km_card = QFrame()
        km_card.setStyleSheet(CARD_STYLE)
        km_card_layout = QVBoxLayout(km_card)
        km_card_layout.setContentsMargins(16, 16, 16, 16)

        km_title = QLabel("📈  Weekly Volume")
        km_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        km_title.setStyleSheet("color: #1A1A2E; border: none;")
        km_card_layout.addWidget(km_title)

        self.km_plot = pg.PlotWidget()
        self.km_plot.setBackground("w")
        self.km_plot.setMinimumHeight(220)
        self.km_plot.showGrid(x=False, y=True, alpha=0.15)
        self.km_plot.getAxis("left").setLabel("km")
        self.km_plot.getAxis("bottom").setLabel("Week")
        self.km_plot.getAxis("left").setPen(pg.mkPen("#888"))
        self.km_plot.getAxis("bottom").setPen(pg.mkPen("#888"))
        self.km_plot.getAxis("left").setTextPen(pg.mkPen("#555"))
        self.km_plot.getAxis("bottom").setTextPen(pg.mkPen("#555"))
        km_card_layout.addWidget(self.km_plot)

        charts_layout.addWidget(km_card, stretch=3)

        # Session type bar chart
        bar_card = QFrame()
        bar_card.setStyleSheet(CARD_STYLE)
        bar_card_layout = QVBoxLayout(bar_card)
        bar_card_layout.setContentsMargins(16, 16, 16, 16)

        bar_title = QLabel("📊  Session Distribution")
        bar_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        bar_title.setStyleSheet("color: #1A1A2E; border: none;")
        bar_card_layout.addWidget(bar_title)

        self.bar_plot = pg.PlotWidget()
        self.bar_plot.setBackground("w")
        self.bar_plot.setMinimumHeight(220)
        self.bar_plot.showGrid(x=False, y=True, alpha=0.15)
        self.bar_plot.getAxis("left").setLabel("Count")
        self.bar_plot.getAxis("left").setPen(pg.mkPen("#888"))
        self.bar_plot.getAxis("bottom").setPen(pg.mkPen("#888"))
        self.bar_plot.getAxis("left").setTextPen(pg.mkPen("#555"))
        self.bar_plot.getAxis("bottom").setTextPen(pg.mkPen("#555"))
        bar_card_layout.addWidget(self.bar_plot)

        charts_layout.addWidget(bar_card, stretch=2)

        self.main_layout.addLayout(charts_layout)

        # ── Pace zones card ──
        self.zones_card = QFrame()
        self.zones_card.setStyleSheet(CARD_STYLE)
        zones_layout = QVBoxLayout(self.zones_card)
        zones_layout.setContentsMargins(16, 16, 16, 16)

        zones_title = QLabel("🎯  Pace Zones")
        zones_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        zones_title.setStyleSheet("color: #1A1A2E; border: none;")
        zones_layout.addWidget(zones_title)

        self.zones_grid = QGridLayout()
        self.zones_grid.setSpacing(8)
        zones_layout.addLayout(self.zones_grid)

        self.main_layout.addWidget(self.zones_card)
        self.main_layout.addStretch()

        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def set_plan(self, plan: FullPlan):
        """Load a plan and refresh all dashboard elements."""
        self.current_plan = plan
        self._refresh()

    def _on_filter_changed(self, idx):
        filters = ["4w", "3m", "all"]
        self.filter_range = filters[idx]
        self._refresh()

    def _refresh(self):
        if not self.current_plan:
            return

        db = get_database()
        plan = self.current_plan

        # Determine date range filter
        today = date.today()
        if self.filter_range == "4w":
            start_date = today - timedelta(weeks=4)
        elif self.filter_range == "3m":
            start_date = today - timedelta(days=90)
        else:
            start_date = date(2000, 1, 1)

        # Get stats
        all_sessions = db.get_all_sessions(plan.id)
        filtered = [s for s in all_sessions
                    if s.date >= start_date and s.session_type != "Rest"]

        # Summary cards
        total_km = sum(s.distance_km for s in filtered)
        completed = sum(1 for s in filtered if s.status == "completed")
        planned = len(filtered)
        longest = max((s.distance_km for s in filtered), default=0)
        paces = [s.pace_target_min_km for s in filtered
                 if s.pace_target_min_km and s.status == "completed"]
        avg_pace = sum(paces) / len(paces) if paces else 0

        # This week's km
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        this_week = [s for s in all_sessions
                     if week_start <= s.date <= week_end and s.session_type != "Rest"]
        week_km = sum(s.distance_km for s in this_week)

        self.card_weekly_km.update_value(f"{week_km:.1f}")
        self.card_avg_pace.update_value(format_pace(avg_pace) if avg_pace else "—")
        self.card_sessions.update_value(f"{completed}/{planned}")
        self.card_longest.update_value(f"{longest:.1f}")

        # Weekly km chart
        self._update_km_chart(plan)

        # Session distribution chart
        self._update_bar_chart(plan)

        # Pace zones
        self._update_zones(plan.pace_zones)

    def _update_km_chart(self, plan: FullPlan):
        self.km_plot.clear()

        weekly_stats = get_database().get_weekly_stats(plan.id)
        if not weekly_stats:
            return

        weeks = list(range(1, len(weekly_stats) + 1))
        kms = [s["total_km"] or 0 for s in weekly_stats]

        # Plot the line
        pen = pg.mkPen(color="#6C63FF", width=3)
        self.km_plot.plot(weeks, kms, pen=pen, symbol="o",
                         symbolSize=6, symbolBrush="#6C63FF",
                         symbolPen=pg.mkPen("#fff", width=1.5))

        # Fill under curve
        fill = pg.FillBetweenItem(
            pg.PlotDataItem(weeks, kms),
            pg.PlotDataItem(weeks, [0] * len(weeks)),
            brush=pg.mkBrush(108, 99, 255, 30),
        )
        self.km_plot.addItem(fill)

    def _update_bar_chart(self, plan: FullPlan):
        self.bar_plot.clear()

        dist_data = get_database().get_session_type_distribution(plan.id)
        if not dist_data:
            return

        types = [d["type"] for d in dist_data]
        counts = [d["count"] for d in dist_data]
        colors = [SESSION_COLORS.get(t, "#888") for t in types]

        x = list(range(len(types)))

        for i, (xi, c, color) in enumerate(zip(x, counts, colors)):
            bar = pg.BarGraphItem(
                x=[xi], height=[c], width=0.6,
                brush=pg.mkBrush(color),
                pen=pg.mkPen(color, width=0.5),
            )
            self.bar_plot.addItem(bar)

        # X-axis labels
        ax = self.bar_plot.getAxis("bottom")
        ax.setTicks([list(zip(x, types))])

    def _update_zones(self, zones: list[PaceZone]):
        # Clear existing
        while self.zones_grid.count():
            item = self.zones_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not zones:
            return

        # Headers
        for col, header_text in enumerate(["Zone", "Fast Pace", "Slow Pace", ""]):
            lbl = QLabel(f"<b>{header_text}</b>")
            lbl.setStyleSheet("color: #666; font-size: 11px; border: none; padding: 4px;")
            self.zones_grid.addWidget(lbl, 0, col)

        for row, zone in enumerate(zones, start=1):
            color = ZONE_COLORS.get(zone.zone_name, "#333")

            name_lbl = QLabel(f'<span style="color:{color}; font-weight:bold;">'
                              f'● {zone.zone_name}</span>')
            name_lbl.setStyleSheet("border: none; padding: 4px; font-size: 13px;")
            self.zones_grid.addWidget(name_lbl, row, 0)

            fast_lbl = QLabel(f"{format_pace(zone.min_pace_min_km)} min/km")
            fast_lbl.setStyleSheet("color: #1A1A2E; border: none; padding: 4px; font-size: 13px;")
            self.zones_grid.addWidget(fast_lbl, row, 1)

            slow_lbl = QLabel(f"{format_pace(zone.max_pace_min_km)} min/km")
            slow_lbl.setStyleSheet("color: #1A1A2E; border: none; padding: 4px; font-size: 13px;")
            self.zones_grid.addWidget(slow_lbl, row, 2)

            desc_lbl = QLabel(f'<span style="color:#777;">{zone.description}</span>')
            desc_lbl.setStyleSheet("border: none; padding: 4px; font-size: 12px;")
            self.zones_grid.addWidget(desc_lbl, row, 3)

    def _open_pace_calc(self):
        dlg = PaceCalculatorDialog(self)
        dlg.exec()
