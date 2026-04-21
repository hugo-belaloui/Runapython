"""
Shared UI constants — colors, formatters, and style strings.
Single source of truth for all visual constants used across the UI layer.
"""

# ═══════════════════════════════════════════════════════════════════════════
# Color palettes
# ═══════════════════════════════════════════════════════════════════════════

# Training session type colors
SESSION_COLORS = {
    "Easy": "#22C55E",
    "Long Run": "#A855F7",
    "Tempo": "#F59E0B",
    "Intervals": "#EF4444",
    "Rest": "#9CA3AF",
    "Race": "#EC4899",
}

# Light background tints for session types
SESSION_BG_COLORS = {
    "Easy": "#F0FDF4",
    "Long Run": "#FAF5FF",
    "Tempo": "#FFFBEB",
    "Intervals": "#FEF2F2",
    "Rest": "#F9FAFB",
    "Race": "#FDF2F8",
}

# Pace zone colors (Daniels zones)
ZONE_COLORS = {
    "Easy": "#22C55E",
    "Marathon": "#3B82F6",
    "Threshold": "#F59E0B",
    "Interval": "#EF4444",
    "Repetition": "#A855F7",
}

# Phase colors (training periodization)
PHASE_COLORS = {
    "Base": "#6C63FF",
    "Build 1": "#F59E0B",
    "Build 2": "#EF4444",
    "Taper": "#22C55E",
    "Race Week": "#EC4899",
}

# ═══════════════════════════════════════════════════════════════════════════
# Common widget styles
# ═══════════════════════════════════════════════════════════════════════════

CARD_STYLE = """
    background: white;
    border: 1px solid #E8E8F0;
    border-radius: 12px;
    padding: 20px;
"""

DIALOG_STYLE = """
QDialog {
    background-color: #F5F5FA;
}
QGroupBox {
    font-weight: bold;
    font-size: 14px;
    color: #1A1A2E;
    border: 1px solid #E0E0E8;
    border-radius: 8px;
    margin-top: 18px;
    background: white;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
}
QLabel {
    color: #333;
    font-size: 13px;
}
QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox {
    padding: 6px 10px;
    border: 1px solid #D0D0D8;
    border-radius: 6px;
    background: white;
    color: #1A1A2E;
    font-size: 13px;
    min-height: 28px;
}
QComboBox:focus, QDateEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus {
    border-color: #6C63FF;
}
QComboBox QAbstractItemView {
    background: white;
    color: #1A1A2E;
    selection-background-color: #6C63FF;
    selection-color: white;
}
QPushButton {
    padding: 8px 20px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    min-height: 32px;
}
QPushButton#primaryBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6C63FF, stop:1 #8B5CF6);
    color: white;
    border: none;
}
QPushButton#primaryBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #5B52E0, stop:1 #7C4FE0);
}
QPushButton#secondaryBtn {
    background: white;
    color: #6C63FF;
    border: 1px solid #6C63FF;
}
QPushButton#secondaryBtn:hover {
    background: #F0EEFF;
}
QPushButton#dangerBtn {
    background: #EF4444;
    color: white;
    border: none;
}
QPushButton#dangerBtn:hover {
    background: #DC2626;
}
"""


# ═══════════════════════════════════════════════════════════════════════════
# Formatters
# ═══════════════════════════════════════════════════════════════════════════

def format_pace(pace: float) -> str:
    """Format pace (min/km) as M:SS."""
    mins = int(pace)
    secs = int((pace - mins) * 60)
    return f"{mins}:{secs:02d}"


def format_time(minutes: float) -> str:
    """Format total minutes as H:MM:SS or M:SS."""
    h = int(minutes // 60)
    m = int(minutes % 60)
    s = int((minutes * 60) % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
