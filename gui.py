import sys
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import calendar
import random
import uuid

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QScrollArea, QSplitter, QFrame, QLineEdit,
    QDateTimeEdit, QSpinBox, QFormLayout, QMessageBox, QComboBox,
    QGridLayout, QDialog
)
from PySide6.QtCore import Qt, QDateTime, QDate, QTime, QSize
from PySide6.QtGui import QColor, QPalette, QFont

from organizer import Assignment, ScheduledAssignment, TimeSlot, UserPreferences
from gemini import schedule_assignments, create_scheduled_assignments, format_duration


class ColorManager:
    """Manages colors for assignments"""
    
    def __init__(self):
        self.color_map = {}
        self.colors = [
            "#FFD700",  # Gold
            "#FF6347",  # Tomato
            "#4682B4",  # Steel Blue
            "#32CD32",  # Lime Green
            "#9370DB",  # Medium Purple
            "#20B2AA",  # Light Sea Green
            "#FF69B4",  # Hot Pink
            "#FF8C00",  # Dark Orange
            "#00CED1",  # Dark Turquoise
            "#BA55D3",  # Medium Orchid
        ]
    
    def get_color(self, assignment_name: str) -> str:
        """Get a consistent color for an assignment"""
        if assignment_name not in self.color_map:
            self.color_map[assignment_name] = self.colors[len(self.color_map) % len(self.colors)]
        return self.color_map[assignment_name]


class TimeSlotItem(QFrame):
    """Widget to represent a time slot"""
    
    def __init__(self, time_slot: TimeSlot, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.time_slot = time_slot
        self.on_edit = on_edit
        self.on_delete = on_delete
        
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(1)
        self.setCursor(Qt.PointingHandCursor)  # Change cursor to indicate clickable
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        
        # Format the start time
        start_time_str = time_slot.start.strftime("%I:%M %p")
        date_str = time_slot.start.strftime("%a, %b %d")
        
        # Format the duration
        duration_str = format_duration(time_slot.duration)
        
        # Create labels
        self.date_label = QLabel(date_str)
        self.date_label.setAlignment(Qt.AlignCenter)
        self.date_label.setFont(QFont("Arial", 8, QFont.Bold))
        
        self.time_label = QLabel(f"⏰ {start_time_str}")
        self.time_label.setFont(QFont("Arial", 8))
        
        self.duration_label = QLabel(f"⏱️ {duration_str}")
        self.duration_label.setFont(QFont("Arial", 8))
        
        # Add buttons layout
        button_layout = QHBoxLayout()
        
        # Edit button
        self.edit_button = QPushButton("✏️")
        self.edit_button.setFixedSize(20, 20)
        self.edit_button.setToolTip("Edit time slot")
        self.edit_button.clicked.connect(self.edit_slot)
        
        # Delete button
        self.delete_button = QPushButton("❌")
        self.delete_button.setFixedSize(20, 20)
        self.delete_button.setToolTip("Delete time slot")
        self.delete_button.clicked.connect(self.delete_slot)
        
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.delete_button)
        button_layout.setAlignment(Qt.AlignRight)
        
        # Add to layout
        layout.addWidget(self.date_label)
        layout.addWidget(self.time_label)
        layout.addWidget(self.duration_label)
        layout.addLayout(button_layout)
        
        self.setMinimumHeight(75)  # Increased to accommodate buttons
    
    def mousePressEvent(self, event):
        """Handle mouse press events for editing"""
        super().mousePressEvent(event)
        self.edit_slot()
    
    def edit_slot(self):
        """Edit this time slot"""
        if self.on_edit:
            self.on_edit(self.time_slot)
    
    def delete_slot(self):
        """Delete this time slot"""
        if self.on_delete:
            self.on_delete(self.time_slot)


class ScheduledAssignmentItem(QFrame):
    """Widget to represent a scheduled assignment"""
    
    def __init__(self, scheduled_assignment: ScheduledAssignment, color_manager: ColorManager, parent=None):
        super().__init__(parent)
        self.scheduled_assignment = scheduled_assignment
        
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(1)
        
        # Set background color based on assignment
        color = color_manager.get_color(scheduled_assignment.name)
        self.setStyleSheet(f"background-color: {color}; border-radius: 5px;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)  # Reduced margins
        layout.setSpacing(2)  # Reduced spacing
        
        # Get session information
        session_duration = getattr(scheduled_assignment, 'session_duration', scheduled_assignment.expected_completion_time)
        session_number = getattr(scheduled_assignment, 'session_number', 1)
        
        # Format time
        time_str = scheduled_assignment.assigned_date.strftime("%I:%M %p")
        
        # Create labels with reduced font size
        assignment_name = scheduled_assignment.name
        if session_number > 1:
            assignment_name += f" (Session {session_number})"
            
        self.name_label = QLabel(assignment_name)
        self.name_label.setFont(QFont("Arial", 8, QFont.Bold))  # Reduced font size
        self.name_label.setWordWrap(True)
        
        self.time_label = QLabel(f"⏰ {time_str}")
        self.time_label.setFont(QFont("Arial", 8))  # Reduced font size
        
        self.duration_label = QLabel(f"⏱️ {format_duration(session_duration)}")
        self.duration_label.setFont(QFont("Arial", 8))  # Reduced font size
        
        # Add to layout
        layout.addWidget(self.name_label)
        layout.addWidget(self.time_label)
        layout.addWidget(self.duration_label)


class DayWidget(QFrame):
    """Widget to display a single day in the calendar view"""
    
    def __init__(self, date: datetime, parent=None, on_edit_slot=None, on_delete_slot=None):
        super().__init__(parent)
        self.date = date
        self.scheduled_assignments = []
        self.time_slots = []
        self.on_edit_slot = on_edit_slot
        self.on_delete_slot = on_delete_slot
        
        self.setFrameStyle(QFrame.Box | QFrame.Sunken)
        self.setLineWidth(1)
        
        # Check if this is today
        today = datetime.now().date()
        if date.date() == today:
            self.setStyleSheet("background-color: #f0f8ff;")  # Light blue for today
        elif date.weekday() >= 5:  # Weekend
            self.setStyleSheet("background-color: #f5f5f5;")  # Light grey for weekend
        
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignTop)
        self.layout.setContentsMargins(3, 3, 3, 3)
        
        # Day header
        self.header = QLabel(date.strftime("%a, %b %d"))
        self.header.setAlignment(Qt.AlignCenter)
        self.header.setFont(QFont("Arial", 9, QFont.Bold))
        
        # Container for assignments and time slots
        self.items_container = QWidget()
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setAlignment(Qt.AlignTop)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(3)
        
        # Scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.items_container)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Add to main layout
        self.layout.addWidget(self.header)
        self.layout.addWidget(self.scroll_area)
    
    def add_scheduled_assignment(self, scheduled_assignment: ScheduledAssignment, color_manager: ColorManager):
        """Add a scheduled assignment to this day"""
        self.scheduled_assignments.append(scheduled_assignment)
        item = ScheduledAssignmentItem(scheduled_assignment, color_manager)
        self.items_layout.addWidget(item)
    
    def add_time_slot(self, time_slot: TimeSlot):
        """Add a time slot to this day"""
        self.time_slots.append(time_slot)
        item = TimeSlotItem(
            time_slot,
            on_edit=self.on_edit_slot,
            on_delete=self.on_delete_slot
        )
        self.items_layout.addWidget(item)


class CalendarView(QWidget):
    """Calendar view widget to display scheduled assignments and time slots"""
    
    def __init__(self, parent=None, on_edit_slot=None, on_delete_slot=None):
        super().__init__(parent)
        self.color_manager = ColorManager()
        self.on_edit_slot = on_edit_slot
        self.on_delete_slot = on_delete_slot
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Calendar grid
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(6)
        
        # Week labels
        for col in range(7):
            day_name = calendar.day_name[col]
            label = QLabel(day_name)
            label.setAlignment(Qt.AlignCenter)
            label.setFont(QFont("Arial", 10, QFont.Bold))
            self.grid_layout.addWidget(label, 0, col)
        
        # Create the calendar days (5 weeks)
        self.days = {}
        today = datetime.now()
        start_day = today - timedelta(days=today.weekday())  # Start from Monday
        
        for week in range(5):
            for day in range(7):
                current_date = start_day + timedelta(days=7*week + day)
                day_widget = DayWidget(
                    current_date,
                    on_edit_slot=self.on_edit_slot,
                    on_delete_slot=self.on_delete_slot
                )
                self.grid_layout.addWidget(day_widget, week+1, day)
                self.days[current_date.date()] = day_widget
                
                # Make column and row sizes even
                self.grid_layout.setColumnMinimumWidth(day, 140)
            
            self.grid_layout.setRowMinimumHeight(week+1, 140)
        
        # Set up the layout
        layout.addLayout(self.grid_layout)
    
    def display_scheduled_assignments(self, scheduled_assignments: List[ScheduledAssignment]):
        """Display scheduled assignments on the calendar"""
        # Clear existing assignments
        self.clear_scheduled_assignments()
        
        # Add new assignments
        for assignment in scheduled_assignments:
            date = assignment.assigned_date.date()
            if date in self.days:
                self.days[date].add_scheduled_assignment(assignment, self.color_manager)
    
    def display_time_slots(self, time_slots: List[TimeSlot]):
        """Display time slots on the calendar"""
        # Clear existing time slots
        self.clear_time_slots()
        
        # Add new time slots
        for slot in time_slots:
            date = slot.start.date()
            if date in self.days:
                self.days[date].add_time_slot(slot)
    
    def clear_scheduled_assignments(self):
        """Clear all scheduled assignments from the calendar"""
        for day_widget in self.days.values():
            for assignment in day_widget.scheduled_assignments:
                for i in reversed(range(day_widget.items_layout.count())):
                    widget = day_widget.items_layout.itemAt(i).widget()
                    if isinstance(widget, ScheduledAssignmentItem):
                        widget.setParent(None)
            day_widget.scheduled_assignments = []
    
    def clear_time_slots(self):
        """Clear all time slots from the calendar"""
        for day_widget in self.days.values():
            for slot in day_widget.time_slots:
                for i in reversed(range(day_widget.items_layout.count())):
                    widget = day_widget.items_layout.itemAt(i).widget()
                    if isinstance(widget, TimeSlotItem):
                        widget.setParent(None)
            day_widget.time_slots = []


class AssignmentDialog(QDialog):
    """Dialog for adding a new assignment"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Assignment")
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface"""
        layout = QFormLayout(self)
        
        # Name field
        self.name_edit = QLineEdit()
        layout.addRow("Name:", self.name_edit)
        
        # Due date field
        self.due_date_edit = QDateTimeEdit()
        self.due_date_edit.setDateTime(QDateTime.currentDateTime().addDays(7))
        self.due_date_edit.setCalendarPopup(True)
        layout.addRow("Due Date:", self.due_date_edit)
        
        # Expected completion time
        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(0, 100)
        self.hours_spin.setSuffix(" hours")
        
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(0, 59)
        self.minutes_spin.setSuffix(" minutes")
        
        time_layout = QHBoxLayout()
        time_layout.addWidget(self.hours_spin)
        time_layout.addWidget(self.minutes_spin)
        
        layout.addRow("Expected Time:", time_layout)
        
        # Add button
        self.add_button = QPushButton("Add Assignment")
        self.add_button.clicked.connect(self.accept)
        layout.addRow("", self.add_button)
    
    def get_assignment(self) -> Assignment:
        """Get the assignment from the dialog"""
        name = self.name_edit.text()
        due_date = self.due_date_edit.dateTime().toPython()
        hours = self.hours_spin.value()
        minutes = self.minutes_spin.value()
        
        expected_time = timedelta(hours=hours, minutes=minutes)
        
        return Assignment(name, due_date, expected_time)


class TimeSlotDialog(QDialog):
    """Dialog for adding a new time slot"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Time Slot")
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface"""
        layout = QFormLayout(self)
        
        # Start date and time
        self.date_edit = QDateTimeEdit()
        self.date_edit.setDateTime(QDateTime.currentDateTime())
        self.date_edit.setCalendarPopup(True)
        layout.addRow("Start Time:", self.date_edit)
        
        # Duration
        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(0, 24)
        self.hours_spin.setSuffix(" hours")
        
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(0, 59)
        self.minutes_spin.setSuffix(" minutes")
        
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(self.hours_spin)
        duration_layout.addWidget(self.minutes_spin)
        
        layout.addRow("Duration:", duration_layout)
        
        # Add button
        self.add_button = QPushButton("Add Time Slot")
        self.add_button.clicked.connect(self.accept)
        layout.addRow("", self.add_button)
    
    def get_time_slot(self) -> TimeSlot:
        """Get the time slot from the dialog"""
        start = self.date_edit.dateTime().toPython()
        hours = self.hours_spin.value()
        minutes = self.minutes_spin.value()
        
        duration = timedelta(hours=hours, minutes=minutes)
        
        return TimeSlot(start, duration)


class PreferencesDialog(QDialog):
    """Dialog for setting user preferences"""
    
    def __init__(self, preferences: Optional[UserPreferences] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("User Preferences")
        self.preferences = preferences or UserPreferences(
            min_study_length=timedelta(minutes=30),
            max_study_length=timedelta(hours=2),
            min_break_length=timedelta(minutes=5),
            max_break_length=timedelta(minutes=15)
        )
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface"""
        layout = QFormLayout(self)
        
        # Min study length
        self.min_study_hours = QSpinBox()
        self.min_study_hours.setRange(0, 24)
        self.min_study_hours.setSuffix(" hours")
        self.min_study_hours.setValue(int(self.preferences.min_study_length.total_seconds() // 3600))
        
        self.min_study_minutes = QSpinBox()
        self.min_study_minutes.setRange(0, 59)
        self.min_study_minutes.setSuffix(" minutes")
        self.min_study_minutes.setValue(int((self.preferences.min_study_length.total_seconds() % 3600) // 60))
        
        min_study_layout = QHBoxLayout()
        min_study_layout.addWidget(self.min_study_hours)
        min_study_layout.addWidget(self.min_study_minutes)
        
        layout.addRow("Min Study Length:", min_study_layout)
        
        # Max study length
        self.max_study_hours = QSpinBox()
        self.max_study_hours.setRange(0, 24)
        self.max_study_hours.setSuffix(" hours")
        self.max_study_hours.setValue(int(self.preferences.max_study_length.total_seconds() // 3600))
        
        self.max_study_minutes = QSpinBox()
        self.max_study_minutes.setRange(0, 59)
        self.max_study_minutes.setSuffix(" minutes")
        self.max_study_minutes.setValue(int((self.preferences.max_study_length.total_seconds() % 3600) // 60))
        
        max_study_layout = QHBoxLayout()
        max_study_layout.addWidget(self.max_study_hours)
        max_study_layout.addWidget(self.max_study_minutes)
        
        layout.addRow("Max Study Length:", max_study_layout)
        
        # Min break length
        self.min_break_hours = QSpinBox()
        self.min_break_hours.setRange(0, 24)
        self.min_break_hours.setSuffix(" hours")
        self.min_break_hours.setValue(int(self.preferences.min_break_length.total_seconds() // 3600))
        
        self.min_break_minutes = QSpinBox()
        self.min_break_minutes.setRange(0, 59)
        self.min_break_minutes.setSuffix(" minutes")
        self.min_break_minutes.setValue(int((self.preferences.min_break_length.total_seconds() % 3600) // 60))
        
        min_break_layout = QHBoxLayout()
        min_break_layout.addWidget(self.min_break_hours)
        min_break_layout.addWidget(self.min_break_minutes)
        
        layout.addRow("Min Break Length:", min_break_layout)
        
        # Max break length
        self.max_break_hours = QSpinBox()
        self.max_break_hours.setRange(0, 24)
        self.max_break_hours.setSuffix(" hours")
        self.max_break_hours.setValue(int(self.preferences.max_break_length.total_seconds() // 3600))
        
        self.max_break_minutes = QSpinBox()
        self.max_break_minutes.setRange(0, 59)
        self.max_break_minutes.setSuffix(" minutes")
        self.max_break_minutes.setValue(int((self.preferences.max_break_length.total_seconds() % 3600) // 60))
        
        max_break_layout = QHBoxLayout()
        max_break_layout.addWidget(self.max_break_hours)
        max_break_layout.addWidget(self.max_break_minutes)
        
        layout.addRow("Max Break Length:", max_break_layout)
        
        # Save button
        self.save_button = QPushButton("Save Preferences")
        self.save_button.clicked.connect(self.accept)
        layout.addRow("", self.save_button)
    
    def get_preferences(self) -> UserPreferences:
        """Get the preferences from the dialog"""
        min_study_length = timedelta(
            hours=self.min_study_hours.value(),
            minutes=self.min_study_minutes.value()
        )
        
        max_study_length = timedelta(
            hours=self.max_study_hours.value(),
            minutes=self.max_study_minutes.value()
        )
        
        min_break_length = timedelta(
            hours=self.min_break_hours.value(),
            minutes=self.min_break_minutes.value()
        )
        
        max_break_length = timedelta(
            hours=self.max_break_hours.value(),
            minutes=self.max_break_minutes.value()
        )
        
        return UserPreferences(
            min_study_length=min_study_length,
            max_study_length=max_study_length,
            min_break_length=min_break_length,
            max_break_length=max_break_length
        )


class MainWindow(QMainWindow):
    """Main window for the application"""
    
    def __init__(self):
        super().__init__()
        self.assignments = []
        self.scheduled_assignments = []
        self.time_slots = []
        self.preferences = UserPreferences(
            min_study_length=timedelta(minutes=30),
            max_study_length=timedelta(hours=2),
            min_break_length=timedelta(minutes=5),
            max_break_length=timedelta(minutes=15)
        )
        
        self.data_file = "jamaai_data.json"
        
        self.setup_ui()
        self.load_data()
    
    def setup_ui(self):
        """Set up the user interface"""
        self.setWindowTitle("JAMAi Assignment Organizer")
        self.setMinimumSize(1000, 700)
        
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(10)
        
        # Top controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)
        
        self.add_assignment_button = QPushButton("Add Assignment")
        self.add_assignment_button.clicked.connect(self.add_assignment)
        
        self.add_time_slot_button = QPushButton("Add Time Slot")
        self.add_time_slot_button.clicked.connect(self.add_time_slot)
        
        self.preferences_button = QPushButton("Preferences")
        self.preferences_button.clicked.connect(self.edit_preferences)
        
        self.schedule_button = QPushButton("Schedule Assignments")
        self.schedule_button.clicked.connect(self.schedule_assignments)
        self.schedule_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        
        # Clear buttons
        self.clear_schedule_button = QPushButton("Clear Schedule")
        self.clear_schedule_button.clicked.connect(self.clear_schedule)
        self.clear_schedule_button.setStyleSheet("background-color: #f44336; color: white;")
        
        controls_layout.addWidget(self.add_assignment_button)
        controls_layout.addWidget(self.add_time_slot_button)
        controls_layout.addWidget(self.preferences_button)
        controls_layout.addWidget(self.schedule_button)
        controls_layout.addWidget(self.clear_schedule_button)
        
        # Calendar view
        self.calendar_view = CalendarView(
            on_edit_slot=self.edit_time_slot,
            on_delete_slot=self.delete_time_slot
        )
        
        # Add to main layout
        main_layout.addLayout(controls_layout)
        main_layout.addWidget(self.calendar_view)
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
        # Set central widget
        self.setCentralWidget(main_widget)
    
    def closeEvent(self, event):
        """Save data when the application is closed"""
        self.save_data()
        super().closeEvent(event)
    
    def save_data(self):
        """Save assignments, time slots and preferences to a JSON file"""
        try:
            data = {
                "assignments": [self.serialize_assignment(a) for a in self.assignments],
                "time_slots": [self.serialize_time_slot(ts) for ts in self.time_slots],
                "scheduled_assignments": [self.serialize_scheduled_assignment(sa) for sa in self.scheduled_assignments],
                "preferences": self.serialize_preferences(self.preferences)
            }
            
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.statusBar().showMessage(f"Data saved to {self.data_file}")
        except Exception as e:
            self.statusBar().showMessage(f"Error saving data: {str(e)}")
    
    def load_data(self):
        """Load assignments, time slots and preferences from a JSON file"""
        if not os.path.exists(self.data_file):
            self.statusBar().showMessage("No saved data found")
            return
        
        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
            
            # Load assignments
            self.assignments = [self.deserialize_assignment(a) for a in data.get("assignments", [])]
            
            # Load time slots
            self.time_slots = [self.deserialize_time_slot(ts) for ts in data.get("time_slots", [])]
            
            # Load scheduled assignments
            self.scheduled_assignments = [self.deserialize_scheduled_assignment(sa) for sa in data.get("scheduled_assignments", [])]
            
            # Load preferences
            if "preferences" in data:
                self.preferences = self.deserialize_preferences(data["preferences"])
            
            self.statusBar().showMessage(f"Loaded {len(self.assignments)} assignments and {len(self.time_slots)} time slots")
            self.update_display()
        except Exception as e:
            self.statusBar().showMessage(f"Error loading data: {str(e)}")
    
    @staticmethod
    def serialize_assignment(assignment: Assignment) -> Dict:
        """Convert an Assignment object to a dictionary for JSON serialization"""
        return {
            "name": assignment.name,
            "due_date": assignment.due_date.isoformat(),
            "expected_completion_time": assignment.expected_completion_time.total_seconds()
        }
    
    @staticmethod
    def deserialize_assignment(data: Dict) -> Assignment:
        """Convert a dictionary to an Assignment object"""
        return Assignment(
            name=data["name"],
            due_date=datetime.fromisoformat(data["due_date"]),
            expected_completion_time=timedelta(seconds=data["expected_completion_time"])
        )
    
    @staticmethod
    def serialize_time_slot(time_slot: TimeSlot) -> Dict:
        """Convert a TimeSlot object to a dictionary for JSON serialization"""
        return {
            "start": time_slot.start.isoformat(),
            "duration": time_slot.duration.total_seconds(),
            "id": str(time_slot.id)
        }
    
    @staticmethod
    def deserialize_time_slot(data: Dict) -> TimeSlot:
        """Convert a dictionary to a TimeSlot object"""
        slot = TimeSlot(
            start=datetime.fromisoformat(data["start"]),
            duration=timedelta(seconds=data["duration"])
        )
        
        # Restore the original ID if possible
        try:
            slot.id = uuid.UUID(data["id"])
        except (ValueError, KeyError):
            # If ID is invalid or missing, keep the auto-generated one
            pass
            
        return slot
    
    @staticmethod
    def serialize_scheduled_assignment(sa: ScheduledAssignment) -> Dict:
        """Convert a ScheduledAssignment object to a dictionary for JSON serialization"""
        data = {
            "name": sa.name,
            "due_date": sa.due_date.isoformat(),
            "expected_completion_time": sa.expected_completion_time.total_seconds(),
            "assigned_date": sa.assigned_date.isoformat()
        }
        
        # Add session information if available
        if hasattr(sa, 'session_duration'):
            data["session_duration"] = sa.session_duration.total_seconds()
        
        if hasattr(sa, 'session_number'):
            data["session_number"] = sa.session_number
            
        return data
    
    @staticmethod
    def deserialize_scheduled_assignment(data: Dict) -> ScheduledAssignment:
        """Convert a dictionary to a ScheduledAssignment object"""
        sa = ScheduledAssignment(
            name=data["name"],
            due_date=datetime.fromisoformat(data["due_date"]),
            expected_completion_time=timedelta(seconds=data["expected_completion_time"]),
            assigned_date=datetime.fromisoformat(data["assigned_date"])
        )
        
        # Restore session information if available
        if "session_duration" in data:
            sa.session_duration = timedelta(seconds=data["session_duration"])
        
        if "session_number" in data:
            sa.session_number = data["session_number"]
            
        return sa
    
    @staticmethod
    def serialize_preferences(preferences: UserPreferences) -> Dict:
        """Convert a UserPreferences object to a dictionary for JSON serialization"""
        return {
            "min_study_length": preferences.min_study_length.total_seconds(),
            "max_study_length": preferences.max_study_length.total_seconds(),
            "min_break_length": preferences.min_break_length.total_seconds(),
            "max_break_length": preferences.max_break_length.total_seconds()
        }
    
    @staticmethod
    def deserialize_preferences(data: Dict) -> UserPreferences:
        """Convert a dictionary to a UserPreferences object"""
        return UserPreferences(
            min_study_length=timedelta(seconds=data["min_study_length"]),
            max_study_length=timedelta(seconds=data["max_study_length"]),
            min_break_length=timedelta(seconds=data["min_break_length"]),
            max_break_length=timedelta(seconds=data["max_break_length"])
        )
    
    def add_assignment(self):
        """Add a new assignment"""
        dialog = AssignmentDialog(self)
        if dialog.exec_():
            assignment = dialog.get_assignment()
            self.assignments.append(assignment)
            self.statusBar().showMessage(f"Added assignment: {assignment.name}")
            self.update_display()
            self.save_data()
    
    def add_time_slot(self):
        """Add a new time slot"""
        dialog = TimeSlotDialog(self)
        if dialog.exec_():
            time_slot = dialog.get_time_slot()
            self.time_slots.append(time_slot)
            self.statusBar().showMessage(f"Added time slot: {time_slot.start.strftime('%Y-%m-%d %H:%M')}")
            self.update_display()
            self.save_data()
    
    def edit_time_slot(self, time_slot: TimeSlot):
        """Edit an existing time slot"""
        dialog = TimeSlotDialog(self)
        
        # Set initial values from existing time slot
        dialog.date_edit.setDateTime(QDateTime(time_slot.start))
        
        hours = int(time_slot.duration.total_seconds() // 3600)
        minutes = int((time_slot.duration.total_seconds() % 3600) // 60)
        
        dialog.hours_spin.setValue(hours)
        dialog.minutes_spin.setValue(minutes)
        
        if dialog.exec_():
            # Get updated values
            updated_slot = dialog.get_time_slot()
            
            # Find and replace the time slot
            for i, slot in enumerate(self.time_slots):
                if slot is time_slot:  # Same object
                    self.time_slots[i] = updated_slot
                    break
            
            self.statusBar().showMessage(f"Updated time slot: {updated_slot.start.strftime('%Y-%m-%d %H:%M')}")
            self.update_display()
            self.save_data()
    
    def delete_time_slot(self, time_slot: TimeSlot):
        """Delete a time slot"""
        confirm = QMessageBox.question(
            self,
            "Confirm Deletion",
            "Are you sure you want to delete this time slot?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            # Remove the time slot
            self.time_slots = [slot for slot in self.time_slots if slot is not time_slot]
            self.statusBar().showMessage("Time slot deleted")
            self.update_display()
            self.save_data()
    
    def edit_preferences(self):
        """Edit user preferences"""
        dialog = PreferencesDialog(self.preferences, self)
        if dialog.exec_():
            self.preferences = dialog.get_preferences()
            self.statusBar().showMessage("Updated preferences")
            self.save_data()
    
    def schedule_assignments(self):
        """Schedule assignments using Gemini"""
        if not self.assignments:
            QMessageBox.warning(self, "No Assignments", "Please add some assignments first.")
            return
        
        if not self.time_slots:
            QMessageBox.warning(self, "No Time Slots", "Please add some available time slots first.")
            return
        
        self.statusBar().showMessage("Scheduling assignments with Gemini...")
        
        try:
            # Call the schedule_assignments function from gemini.py
            result = schedule_assignments(self.assignments, self.time_slots, self.preferences)
            
            # Create scheduled assignments from the response
            self.scheduled_assignments = create_scheduled_assignments(result, self.assignments)
            
            self.statusBar().showMessage(f"Scheduled {len(self.scheduled_assignments)} sessions")
            
            # Update the display
            self.update_display()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to schedule assignments: {str(e)}")
            self.statusBar().showMessage("Failed to schedule assignments")
    
    def clear_schedule(self):
        """Clear all scheduled assignments"""
        if not self.scheduled_assignments:
            return
            
        confirm = QMessageBox.question(
            self, 
            "Confirm Clear", 
            "Are you sure you want to clear all scheduled assignments?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            self.scheduled_assignments = []
            self.update_display()
            self.statusBar().showMessage("Schedule cleared")
            self.save_data()
    
    def update_display(self):
        """Update the calendar display"""
        self.calendar_view.display_time_slots(self.time_slots)
        self.calendar_view.display_scheduled_assignments(self.scheduled_assignments)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
