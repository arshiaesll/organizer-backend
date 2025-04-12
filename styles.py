"""
Styling definitions for the JAMAi Assignment Organizer application.
This file contains all CSS styles used throughout the application.
"""

# Colors
SCHEDULED_BG_COLOR = "#E8F5E9"  # Light green for scheduled assignments
UNSCHEDULED_BG_COLOR = "#FFEBEE"  # Light red for unscheduled assignments
TIME_SLOT_BG_COLOR = "rgba(76, 175, 80, 0.2)"  # Transparent green for time slots

# Button styles with smaller font and padding
NORMAL_BUTTON_STYLE = """
    QPushButton {
        background-color: #f5f5f5;
        border: 1px solid #dcdcdc;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 11px;
        color: #333333;
    }
    QPushButton:hover {
        background-color: #e6e6e6;
        border: 1px solid #c0c0c0;
    }
    QPushButton:pressed {
        background-color: #d9d9d9;
    }
"""

WARNING_BUTTON_STYLE = """
    QPushButton {
        background-color: #FF9800;
        border: 1px solid #FB8C00;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 11px;
        color: white;
    }
    QPushButton:hover {
        background-color: #F57C00;
    }
    QPushButton:pressed {
        background-color: #EF6C00;
    }
"""

DANGER_BUTTON_STYLE = """
    QPushButton {
        background-color: #f44336;
        border: 1px solid #e53935;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 11px;
        color: white;
    }
    QPushButton:hover {
        background-color: #e53935;
    }
    QPushButton:pressed {
        background-color: #d32f2f;
    }
"""

SUCCESS_BUTTON_STYLE = """
    QPushButton {
        background-color: #4CAF50;
        border: 1px solid #43A047;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 11px;
        color: white;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #43A047;
    }
    QPushButton:pressed {
        background-color: #388E3C;
    }
"""

# Navigation button styles
NAV_BUTTON_STYLE = """
    QPushButton {
        background-color: #f5f5f5;
        border: 1px solid #dcdcdc;
        border-radius: 4px;
        padding: 3px 6px;
        font-size: 11px;
        color: #333333;
        min-height: 22px;
        max-height: 22px;
    }
    QPushButton:hover {
        background-color: #e6e6e6;
        border: 1px solid #c0c0c0;
    }
    QPushButton:pressed {
        background-color: #d9d9d9;
    }
"""

TODAY_BUTTON_STYLE = """
    QPushButton {
        background-color: #2196F3;
        border: 1px solid #1E88E5;
        border-radius: 4px;
        padding: 3px 6px;
        font-size: 11px;
        font-weight: bold;
        color: white;
        min-height: 22px;
        max-height: 22px;
    }
    QPushButton:hover {
        background-color: #1E88E5;
    }
    QPushButton:pressed {
        background-color: #1976D2;
    }
"""

# Dialog button styles
DIALOG_BUTTON_STYLE = """
    QPushButton {
        background-color: #4CAF50;
        border: 1px solid #43A047;
        border-radius: 4px;
        padding: 3px 6px;
        font-size: 11px;
        color: white;
    }
    QPushButton:hover {
        background-color: #43A047;
    }
    QPushButton:pressed {
        background-color: #388E3C;
    }
"""

# Simplified style helpers
def get_simple_button_style(font_size=11, padding_h=4, padding_v=8):
    """Create a simple button style with specified font size and padding"""
    return f"font-size: {font_size}px; padding: {padding_h}px {padding_v}px;"

def get_colored_button_style(bg_color, text_color="white", font_size=11, padding_h=4, padding_v=8, font_weight=None):
    """Create a colored button style with specified background, text color, font size and padding"""
    style = f"background-color: {bg_color}; color: {text_color}; font-size: {font_size}px; padding: {padding_h}px {padding_v}px;"
    if font_weight:
        style += f" font-weight: {font_weight};"
    return style 