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
    QGridLayout, QDialog, QGroupBox
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
        self.has_assignments = False
        
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
        
        # Assignment indicator (initially hidden)
        self.assignment_label = QLabel("📝 Has assignments")
        self.assignment_label.setFont(QFont("Arial", 7))
        self.assignment_label.setStyleSheet("color: #FF5722;")
        self.assignment_label.setVisible(False)
        
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
        layout.addWidget(self.assignment_label)
        layout.addLayout(button_layout)
        
        self.setMinimumHeight(80)  # Increased to accommodate assignment indicator
    
    def set_has_assignments(self, has_assignments: bool):
        """Set whether this time slot has assignments scheduled in it"""
        self.has_assignments = has_assignments
        self.assignment_label.setVisible(has_assignments)
        
        if has_assignments:
            # Add a border to indicate this slot is being used
            self.setStyleSheet(self.styleSheet() + "border: 2px solid #4CAF50;")
            self.setToolTip("This time slot has scheduled assignments")
    
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
            if self.has_assignments:
                # Show warning before deleting a time slot with assignments
                from PySide6.QtWidgets import QMessageBox
                confirm = QMessageBox.warning(
                    self,
                    "Assignments Scheduled",
                    "This time slot has assignments scheduled in it. Deleting it may affect your schedule.\n\nAre you sure you want to delete it?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if confirm != QMessageBox.Yes:
                    return
                    
            self.on_delete(self.time_slot)


class ScheduledAssignmentItem(QFrame):
    """Widget to represent a scheduled assignment"""
    
    def __init__(self, scheduled_assignment: ScheduledAssignment, color_manager: ColorManager, parent=None):
        super().__init__(parent)
        self.scheduled_assignment = scheduled_assignment
        self.overlapped_with_slot = False
        self.overlapped_slot = None
        
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(1)
        
        # Set background color based on assignment
        color = color_manager.get_color(scheduled_assignment.name)
        self.setStyleSheet(f"background-color: {color}; border-radius: 5px;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        
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
        self.name_label.setFont(QFont("Arial", 8, QFont.Bold))
        self.name_label.setWordWrap(True)
        
        self.time_label = QLabel(f"⏰ {time_str}")
        self.time_label.setFont(QFont("Arial", 8))
        
        self.duration_label = QLabel(f"⏱️ {format_duration(session_duration)}")
        self.duration_label.setFont(QFont("Arial", 8))
        
        # Overlap indicator (initially hidden)
        self.overlap_label = QLabel("⚠️ In available time slot")
        self.overlap_label.setFont(QFont("Arial", 7))
        self.overlap_label.setStyleSheet("color: #FF5722;")
        self.overlap_label.setVisible(False)
        
        # Add to layout
        layout.addWidget(self.name_label)
        layout.addWidget(self.time_label)
        layout.addWidget(self.duration_label)
        layout.addWidget(self.overlap_label)
    
    def set_overlap_with_slot(self, time_slot: TimeSlot):
        """Set that this assignment overlaps with a time slot"""
        self.overlapped_with_slot = True
        self.overlapped_slot = time_slot
        self.overlap_label.setVisible(True)
        
        # Add a border to indicate this assignment uses an available time slot
        self.setStyleSheet(self.styleSheet() + "border: 2px solid #4CAF50;")


class DayWidget(QFrame):
    """Widget to display a single day in the calendar view"""
    
    def __init__(self, date: datetime, parent=None, on_edit_slot=None, on_delete_slot=None, show_hourly=False):
        super().__init__(parent)
        self.date = date
        self.scheduled_assignments = []
        self.time_slots = []
        self.on_edit_slot = on_edit_slot
        self.on_delete_slot = on_delete_slot
        self.show_hourly = show_hourly
        
        self.setFrameStyle(QFrame.Box | QFrame.Sunken)
        self.setLineWidth(1)
        
        # Check if this is today
        today = datetime.now().date()
        if date.date() == today:
            self.setStyleSheet("background-color: #f0f8ff;")  # Light blue for today
        elif date.weekday() >= 5:  # Weekend
            self.setStyleSheet("background-color: #f5f5f5;")  # Light grey for weekend
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface for the day widget"""
        # Create layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(3, 3, 3, 3)
        self.layout.setSpacing(3)
        
        # Day header
        self.header = QLabel(self.date.strftime("%a, %b %d"))
        self.header.setAlignment(Qt.AlignCenter)
        self.header.setFont(QFont("Arial", 9, QFont.Bold))
        
        # Container for items
        self.items_container = QScrollArea()
        self.items_container.setWidgetResizable(True)
        self.items_container.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        if self.show_hourly:
            # Create hourly view
            self.hourly_widget = QWidget()
            self.hourly_layout = QVBoxLayout(self.hourly_widget)
            self.hourly_layout.setContentsMargins(0, 0, 0, 0)
            self.hourly_layout.setSpacing(0)
            self.hourly_layout.setAlignment(Qt.AlignTop)
            
            # Create a container for multi-hour items
            self.multi_hour_widget = QWidget(self.hourly_widget)
            self.multi_hour_widget.setStyleSheet("background-color: transparent;")
            self.multi_hour_widget.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            
            # The multi-hour widget will use an absolute positioning layout
            self.multi_hour_widget.setLayout(QVBoxLayout())
            self.multi_hour_widget.layout().setContentsMargins(0, 0, 0, 0)
            self.multi_hour_widget.layout().setSpacing(0)
            
            # The hours dict will store references to each hour frame and its layout
            self.hours = {}
            
            # Create hour slots (6 AM to 10 PM)
            total_height = 0
            for hour in range(6, 23):
                hour_frame = QFrame()
                hour_frame.setFrameStyle(QFrame.Box | QFrame.Plain)
                hour_frame.setLineWidth(1)
                hour_height = 60  # Height per hour
                hour_frame.setFixedHeight(hour_height)
                
                # Set properties on the frame
                hour_frame.setProperty("hour", hour)
                hour_frame.setObjectName(f"hour_frame_{hour}")  # Set object name for styling
                
                hour_layout = QVBoxLayout(hour_frame)
                hour_layout.setContentsMargins(2, 2, 2, 2)
                hour_layout.setSpacing(1)
                
                # Add hour label to the frame
                time_label = QLabel(f"{hour % 12 or 12} {('AM' if hour < 12 else 'PM')}")
                time_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                time_label.setFont(QFont("Arial", 7))
                time_label.setStyleSheet("color: #888;")
                hour_layout.addWidget(time_label)
                
                # Store the hour frame and layout in our dict
                self.hours[hour] = {
                    'frame': hour_frame,
                    'layout': hour_layout,
                    'y_position': total_height,  # Start of this hour in absolute coordinates
                    'height': hour_height
                }
                
                total_height += hour_height
                self.hourly_layout.addWidget(hour_frame)
            
            # Configure the multi-hour widget to overlay the hour frames
            self.multi_hour_widget.setGeometry(0, 0, self.hourly_widget.width(), total_height)
            self.hourly_widget.resizeEvent = lambda e: self.multi_hour_widget.setGeometry(
                0, 0, self.hourly_widget.width(), total_height
            )
            
            self.items_container.setWidget(self.hourly_widget)
        else:
            # Use simple list view
            self.list_widget = QWidget()
            self.list_layout = QVBoxLayout(self.list_widget)
            self.list_layout.setContentsMargins(0, 0, 0, 0)
            self.list_layout.setSpacing(3)
            self.list_layout.setAlignment(Qt.AlignTop)
            
            self.items_container.setWidget(self.list_widget)
        
        # Add to main layout
        self.layout.addWidget(self.header)
        self.layout.addWidget(self.items_container)
    
    def add_scheduled_assignment(self, scheduled_assignment: ScheduledAssignment, color_manager: ColorManager):
        """Add a scheduled assignment to this day"""
        self.scheduled_assignments.append(scheduled_assignment)
        
        if self.show_hourly:
            # Get the start time and duration
            start_time = scheduled_assignment.assigned_date
            duration = getattr(scheduled_assignment, 'session_duration', scheduled_assignment.expected_completion_time)
            end_time = start_time + duration
            
            # Calculate which hour blocks this assignment spans
            start_hour = start_time.hour
            start_minute = start_time.minute
            end_hour = end_time.hour
            end_minute = end_time.minute
            
            if end_minute > 0 or end_time.second > 0:
                end_hour += 1  # Include the last partial hour
            
            # If it spans multiple hours or has a specific minute offset, add it to the overlay widget
            if (end_hour - start_hour > 1 or start_minute > 0) and start_hour >= 6 and start_hour < 23:
                # Get color for the assignment
                color = color_manager.get_color(scheduled_assignment.name)
                
                # Create a custom multi-hour item
                container = QFrame(self.multi_hour_widget)
                container.setFrameStyle(QFrame.Box | QFrame.Raised)
                container.setLineWidth(1)
                container.setStyleSheet(f"background-color: {color}; border-radius: 5px; border: 1px solid #666;")
                
                container_layout = QVBoxLayout(container)
                container_layout.setContentsMargins(5, 5, 5, 5)
                
                # Get session information
                session_number = getattr(scheduled_assignment, 'session_number', 1)
                
                # Format time
                time_str = scheduled_assignment.assigned_date.strftime("%I:%M %p")
                
                # Create labels with reduced font size
                assignment_name = scheduled_assignment.name
                if session_number > 1:
                    assignment_name += f" (Session {session_number})"
                    
                name_label = QLabel(assignment_name)
                name_label.setFont(QFont("Arial", 9, QFont.Bold))
                name_label.setStyleSheet("color: black;")
                name_label.setWordWrap(True)
                name_label.setAlignment(Qt.AlignCenter)
                
                time_label = QLabel(f"⏰ {time_str}")
                time_label.setFont(QFont("Arial", 8))
                time_label.setStyleSheet("color: black;")
                
                duration_label = QLabel(f"⏱️ {format_duration(duration)}")
                duration_label.setFont(QFont("Arial", 8))
                duration_label.setStyleSheet("color: black;")
                
                # Add to layout
                container_layout.addWidget(name_label)
                container_layout.addWidget(time_label)
                container_layout.addWidget(duration_label)
                container_layout.addStretch()
                
                # Calculate position and size
                hour_info = self.hours.get(start_hour)
                if hour_info:
                    # Calculate precise position based on hour and minute
                    y_position = hour_info['y_position'] + (start_minute / 60.0) * hour_info['height']
                    
                    # Calculate height based on duration in minutes
                    duration_minutes = duration.total_seconds() / 60
                    pixel_height = min(
                        (duration_minutes / 60.0) * hour_info['height'],  # Height based on duration
                        (23 - start_hour - (start_minute / 60.0)) * hour_info['height']  # Max visible height
                    )
                    
                    # Set the position and size - use absolute positioning
                    container.setFixedHeight(max(50, int(pixel_height)))  # Minimum height of 50px
                    container.setGeometry(10, int(y_position), self.hourly_widget.width() - 20, int(pixel_height))
                    container.show()  # Ensure it's visible
            else:
                # For single-hour items, add to the regular hour layout
                # Find the correct hour to place this in
                target_hour = max(6, min(22, start_hour))
                hour_info = self.hours.get(target_hour)
                
                if hour_info:
                    item = ScheduledAssignmentItem(scheduled_assignment, color_manager)
                    hour_info['layout'].addWidget(item)
        else:
            # Simple list view - add normally
            item = ScheduledAssignmentItem(scheduled_assignment, color_manager)
            self.list_layout.addWidget(item)
    
    def add_time_slot(self, time_slot: TimeSlot):
        """Add a time slot to this day - only highlights the hour blocks that contain the time slot"""
        self.time_slots.append(time_slot)
        
        if self.show_hourly:
            # Get the start time and duration
            start_time = time_slot.start
            duration = time_slot.duration
            end_time = start_time + duration
            
            # More precise block highlighting calculation
            duration_seconds = duration.total_seconds()
            start_hour = start_time.hour
            
            # Create a list of hour blocks to highlight
            hours_to_highlight = []
            
            # Exact hour calculation with special handling for one-hour slots
            if 3540 <= duration_seconds <= 3660:  # ~1 hour (allow small margin for rounding)
                # For 1-hour slots, only highlight the starting hour block
                hours_to_highlight.append(start_hour)
            else:
                # For other slots, calculate which hours it spans
                current_time = start_time
                while current_time < end_time:
                    if 6 <= current_time.hour < 23:  # Only highlight visible hours
                        hours_to_highlight.append(current_time.hour)
                    # Move to the next hour
                    next_hour = current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                    if next_hour >= end_time:
                        break
                    current_time = next_hour
            
            # Highlight each hour block in our calculated list
            for hour in hours_to_highlight:
                if 6 <= hour < 23:  # Ensure we only highlight visible hours
                    hour_info = self.hours.get(hour)
                    if hour_info:
                        # Change the background color of the hour frame to indicate a time slot
                        hour_info['frame'].setStyleSheet("background-color: rgba(76, 175, 80, 0.2);")  # Light green with transparency
                        
                        # Add a tooltip to show the time slot info
                        slot_time = start_time.strftime("%I:%M %p")
                        slot_duration = format_duration(duration)
                        hour_info['frame'].setToolTip(f"Available Time Slot: {slot_time}, Duration: {slot_duration}")
                        
                        # Store the time slot reference to allow editing
                        hour_info['frame'].setProperty("time_slot", time_slot.id)
                        
                        # Enable context menu on right click
                        hour_info['frame'].setContextMenuPolicy(Qt.CustomContextMenu)
                        hour_info['frame'].customContextMenuRequested.connect(
                            lambda pos, ts=time_slot: self.show_time_slot_context_menu(pos, ts)
                        )
    
    def show_time_slot_context_menu(self, pos, time_slot):
        """Show a context menu for the time slot when right-clicking on a highlighted hour"""
        from PySide6.QtWidgets import QMenu
        
        menu = QMenu()
        edit_action = menu.addAction("✏️ Edit Time Slot")
        delete_action = menu.addAction("❌ Delete Time Slot")
        
        # Connect actions
        edit_action.triggered.connect(lambda: self.on_edit_slot(time_slot) if self.on_edit_slot else None)
        delete_action.triggered.connect(lambda: self.on_delete_slot(time_slot) if self.on_delete_slot else None)
        
        # Show the menu at the cursor position
        menu.exec_(self.sender().mapToGlobal(pos))
    
    def has_assignment_in_slot(self, time_slot: TimeSlot) -> bool:
        """Check if there's an assignment scheduled in this time slot"""
        # Ensure we're comparing naive or aware datetimes consistently
        slot_start = self.ensure_naive_datetime(time_slot.start)
        slot_end = self.ensure_naive_datetime(slot_start + time_slot.duration)
        
        for assignment in self.scheduled_assignments:
            assignment_start = self.ensure_naive_datetime(assignment.assigned_date)
            session_duration = getattr(assignment, 'session_duration', assignment.expected_completion_time)
            assignment_end = self.ensure_naive_datetime(assignment_start + session_duration)
            
            # Check for overlap - use a stricter overlap detection
            if self.check_overlap(slot_start, slot_end, assignment_start, assignment_end):
                return True
        
        return False
    
    @staticmethod
    def check_overlap(slot_start, slot_end, assignment_start, assignment_end):
        """Check if two time ranges overlap"""
        # Check if there's any overlap at all
        return max(slot_start, assignment_start) < min(slot_end, assignment_end)
    
    @staticmethod
    def ensure_naive_datetime(dt: datetime) -> datetime:
        """Ensure a datetime is naive (no timezone) to avoid comparison issues"""
        if dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        return dt
    
    def clear_scheduled_assignments(self):
        """Clear all scheduled assignments from this day"""
        self.scheduled_assignments = []
        self.clear_widgets(ScheduledAssignmentItem)
    
    def clear_time_slots(self):
        """Clear all time slots from this day"""
        self.time_slots = []
        
        # Reset the styling of all hour frames to remove the green highlighting
        if self.show_hourly:
            for hour_info in self.hours.values():
                hour_info['frame'].setStyleSheet("")
                hour_info['frame'].setToolTip("")
        else:
            # Clear from simple list
            self.clear_widgets(TimeSlotItem)
    
    def clear_all(self):
        """Clear all items from this day"""
        self.scheduled_assignments = []
        self.time_slots = []
        
        if self.show_hourly:
            # Clear all hour layouts
            for hour_info in self.hours.values():
                layout = hour_info['layout']
                # Remove all widgets from the hour layout except the hour label
                for i in reversed(range(layout.count())):
                    if i > 0:  # Keep the hour label (index 0)
                        widget = layout.itemAt(i).widget()
                        if widget:
                            widget.setParent(None)
                
                # Reset the styling of the hour frame
                hour_info['frame'].setStyleSheet("")
                hour_info['frame'].setToolTip("")
            
            # Clear the multi-hour layout
            while self.multi_hour_widget.layout().count():
                widget = self.multi_hour_widget.layout().itemAt(0).widget()
                if widget:
                    widget.setParent(None)
        else:
            # Clear simple list
            while self.list_layout.count():
                widget = self.list_layout.itemAt(0).widget()
                if widget:
                    widget.setParent(None)
    
    def clear_widgets(self, widget_type):
        """Clear widgets of a specific type from this day"""
        if self.show_hourly:
            # Clear from all hour layouts
            for hour_info in self.hours.values():
                layout = hour_info['layout']
                # Remove widgets of the specified type
                for i in reversed(range(layout.count())):
                    widget = layout.itemAt(i).widget()
                    if isinstance(widget, widget_type):
                        widget.setParent(None)
        else:
            # Clear from simple list
            for i in reversed(range(self.list_layout.count())):
                widget = self.list_layout.itemAt(i).widget()
                if isinstance(widget, widget_type):
                    widget.setParent(None)


class CalendarView(QWidget):
    """Calendar view widget to display scheduled assignments and time slots"""
    
    def __init__(self, parent=None, on_edit_slot=None, on_delete_slot=None):
        super().__init__(parent)
        self.color_manager = ColorManager()
        self.on_edit_slot = on_edit_slot
        self.on_delete_slot = on_delete_slot
        self.current_week_start = self.get_current_week_start()
        self.setup_ui()
    
    def get_current_week_start(self):
        """Get the start date of the current week (Monday)"""
        today = datetime.now()
        return today - timedelta(days=today.weekday())
    
    def setup_ui(self):
        """Set up the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Add week navigation controls
        nav_layout = QHBoxLayout()
        
        self.prev_week_btn = QPushButton("◀ Previous Week")
        self.prev_week_btn.clicked.connect(self.show_previous_week)
        
        self.today_btn = QPushButton("Today")
        self.today_btn.clicked.connect(self.show_current_week)
        
        self.next_week_btn = QPushButton("Next Week ▶")
        self.next_week_btn.clicked.connect(self.show_next_week)
        
        self.week_label = QLabel()
        self.week_label.setAlignment(Qt.AlignCenter)
        self.week_label.setFont(QFont("Arial", 12, QFont.Bold))
        
        nav_layout.addWidget(self.prev_week_btn)
        nav_layout.addWidget(self.today_btn)
        nav_layout.addWidget(self.week_label)
        nav_layout.addWidget(self.next_week_btn)
        
        layout.addLayout(nav_layout)
        
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
        
        # Create the calendar days (1 week)
        self.days = {}
        
        # Create time header (hours)
        hours_widget = QWidget()
        hours_layout = QVBoxLayout(hours_widget)
        hours_layout.setContentsMargins(0, 0, 0, 0)
        hours_layout.setSpacing(0)
        
        # Add header spacer to align with day headers
        header_spacer = QLabel("Time")
        header_spacer.setAlignment(Qt.AlignCenter)
        header_spacer.setFont(QFont("Arial", 10, QFont.Bold))
        hours_layout.addWidget(header_spacer)
        
        # Add hours labels (6 AM to 10 PM)
        for hour in range(6, 23):
            hour_label = QLabel(f"{hour % 12 or 12} {('AM' if hour < 12 else 'PM')}")
            hour_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            hour_label.setFont(QFont("Arial", 8))
            hour_label.setFixedHeight(60)  # Height per hour
            hours_layout.addWidget(hour_label)
        
        # Add hours column to grid
        self.grid_layout.addWidget(hours_widget, 1, 0)
        
        # Set up the layout
        layout.addLayout(self.grid_layout)
        
        # Update the calendar with current week
        self.update_calendar()
    
    def update_calendar(self):
        """Update the calendar to show the current week"""
        # Clear existing days
        for day_widget in self.days.values():
            day_widget.setParent(None)
        self.days.clear()
        
        # Update week label
        week_end = self.current_week_start + timedelta(days=6)
        self.week_label.setText(
            f"{self.current_week_start.strftime('%B %d')} - {week_end.strftime('%B %d, %Y')}"
        )
        
        # Create new days for the week
        for day in range(7):
            current_date = self.current_week_start + timedelta(days=day)
            day_widget = DayWidget(
                current_date,
                on_edit_slot=self.on_edit_slot,
                on_delete_slot=self.on_delete_slot,
                show_hourly=True  # Enable hourly view
            )
            self.grid_layout.addWidget(day_widget, 1, day + 1)  # +1 because hour labels are in column 0
            self.days[current_date.date()] = day_widget
            
            # Make column sizes even
            self.grid_layout.setColumnMinimumWidth(day + 1, 200)
        
        # Refresh the display if we have data
        self.update_display()
    
    def update_display(self):
        """Update the display with current assignments and time slots"""
        for day_widget in self.days.values():
            day_widget.clear_all()
        
        # First add all time slots (they'll just highlight the hours)
        self.display_time_slots(getattr(self, '_time_slots', []))
        
        # Then add all scheduled assignments
        self.display_scheduled_assignments(getattr(self, '_scheduled_assignments', []))
    
    def show_previous_week(self):
        """Show the previous week"""
        self.current_week_start -= timedelta(days=7)
        self.update_calendar()
    
    def show_next_week(self):
        """Show the next week"""
        self.current_week_start += timedelta(days=7)
        self.update_calendar()
    
    def show_current_week(self):
        """Show the current week"""
        self.current_week_start = self.get_current_week_start()
        self.update_calendar()
    
    def display_scheduled_assignments(self, scheduled_assignments: List[ScheduledAssignment]):
        """Display scheduled assignments on the calendar"""
        self._scheduled_assignments = scheduled_assignments
        
        # Add new assignments
        for assignment in scheduled_assignments:
            date = assignment.assigned_date.date()
            if date in self.days:
                self.days[date].add_scheduled_assignment(assignment, self.color_manager)
    
    def display_time_slots(self, time_slots: List[TimeSlot]):
        """Display time slots on the calendar"""
        self._time_slots = time_slots
        
        # Add new time slots
        for slot in time_slots:
            date = slot.start.date()
            if date in self.days:
                self.days[date].add_time_slot(slot)
    
    def clear_scheduled_assignments(self):
        """Clear all scheduled assignments from the calendar"""
        for day_widget in self.days.values():
            day_widget.clear_scheduled_assignments()
        self._scheduled_assignments = []
    
    def clear_time_slots(self):
        """Clear all time slots from the calendar"""
        for day_widget in self.days.values():
            day_widget.clear_time_slots()
        self._time_slots = []


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
        
        # Assignment controls group
        assignment_group = QGroupBox("Assignments")
        assignment_layout = QHBoxLayout(assignment_group)
        
        self.add_assignment_button = QPushButton("Add Assignment")
        self.add_assignment_button.clicked.connect(self.add_assignment)
        
        self.clear_assignments_button = QPushButton("Clear All Assignments")
        self.clear_assignments_button.clicked.connect(self.clear_assignments)
        self.clear_assignments_button.setStyleSheet("background-color: #FF9800; color: white;")
        
        assignment_layout.addWidget(self.add_assignment_button)
        assignment_layout.addWidget(self.clear_assignments_button)
        
        # Time slots controls group
        timeslot_group = QGroupBox("Time Slots")
        timeslot_layout = QHBoxLayout(timeslot_group)
        
        self.add_time_slot_button = QPushButton("Add Time Slot")
        self.add_time_slot_button.clicked.connect(self.add_time_slot)
        
        self.clear_time_slots_button = QPushButton("Clear All Time Slots")
        self.clear_time_slots_button.clicked.connect(self.clear_time_slots)
        self.clear_time_slots_button.setStyleSheet("background-color: #FF9800; color: white;")
        
        timeslot_layout.addWidget(self.add_time_slot_button)
        timeslot_layout.addWidget(self.clear_time_slots_button)
        
        # Scheduling controls group
        schedule_group = QGroupBox("Scheduling")
        schedule_layout = QHBoxLayout(schedule_group)
        
        self.preferences_button = QPushButton("Preferences")
        self.preferences_button.clicked.connect(self.edit_preferences)
        
        self.schedule_button = QPushButton("Schedule Assignments")
        self.schedule_button.clicked.connect(self.schedule_assignments)
        self.schedule_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        
        self.clear_schedule_button = QPushButton("Clear Schedule")
        self.clear_schedule_button.clicked.connect(self.clear_schedule)
        self.clear_schedule_button.setStyleSheet("background-color: #f44336; color: white;")
        
        schedule_layout.addWidget(self.preferences_button)
        schedule_layout.addWidget(self.schedule_button)
        schedule_layout.addWidget(self.clear_schedule_button)
        
        # Add control groups to main controls layout
        controls_layout.addWidget(assignment_group)
        controls_layout.addWidget(timeslot_group)
        controls_layout.addWidget(schedule_group)
        
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
        dt = datetime.fromisoformat(data["due_date"])
        # Ensure naive datetime to avoid comparison issues
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
            
        return Assignment(
            name=data["name"],
            due_date=dt,
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
        dt = datetime.fromisoformat(data["start"])
        # Ensure naive datetime to avoid comparison issues
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
            
        slot = TimeSlot(
            start=dt,
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
        due_date = datetime.fromisoformat(data["due_date"])
        assigned_date = datetime.fromisoformat(data["assigned_date"])
        
        # Ensure naive datetimes to avoid comparison issues
        if due_date.tzinfo is not None:
            due_date = due_date.replace(tzinfo=None)
        if assigned_date.tzinfo is not None:
            assigned_date = assigned_date.replace(tzinfo=None)
            
        sa = ScheduledAssignment(
            name=data["name"],
            due_date=due_date,
            expected_completion_time=timedelta(seconds=data["expected_completion_time"]),
            assigned_date=assigned_date
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
        # Create a simplified version to check for overlap
        has_assignments = False
        
        # Check if any assignments are scheduled in this time slot
        for sa in self.scheduled_assignments:
            slot_start = time_slot.start
            slot_end = slot_start + time_slot.duration
            assignment_start = sa.assigned_date
            assignment_end = assignment_start + getattr(sa, 'session_duration', sa.expected_completion_time)
            
            # Make sure both are naive for comparison
            if slot_start.tzinfo is not None:
                slot_start = slot_start.replace(tzinfo=None)
            if slot_end.tzinfo is not None:
                slot_end = slot_end.replace(tzinfo=None)
            if assignment_start.tzinfo is not None:
                assignment_start = assignment_start.replace(tzinfo=None)
            if assignment_end.tzinfo is not None:
                assignment_end = assignment_end.replace(tzinfo=None)
            
            # Check for overlap using the helper method
            if max(slot_start, assignment_start) < min(slot_end, assignment_end):
                has_assignments = True
                break
                
        confirm_text = "Are you sure you want to delete this time slot?"
        if has_assignments:
            confirm_text = "This time slot has assignments scheduled in it. Deleting it may affect your schedule.\n\nAre you sure you want to delete it?"
            
        confirm = QMessageBox.question(
            self,
            "Confirm Deletion",
            confirm_text,
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
            
            # Check for assignments that couldn't be scheduled within available time slots
            total_assignments = len(self.assignments)
            scheduled_assignment_names = set()
            for sa in self.scheduled_assignments:
                scheduled_assignment_names.add(sa.name)
            
            if len(scheduled_assignment_names) < len(self.assignments):
                unscheduled = [a.name for a in self.assignments if a.name not in scheduled_assignment_names]
                QMessageBox.warning(
                    self,
                    "Not All Assignments Scheduled",
                    f"The following assignments could not be scheduled with the current time slots:\n\n" +
                    "\n".join(f"• {name}" for name in unscheduled)
                )
                
            self.statusBar().showMessage(f"Scheduled {len(self.scheduled_assignments)} sessions")
            
            # Update the display
            self.update_display()
            self.save_data()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to schedule assignments: {str(e)}")
            self.statusBar().showMessage("Failed to schedule assignments")
    
    def clear_assignments(self):
        """Clear all assignments"""
        if not self.assignments:
            return
            
        confirm = QMessageBox.question(
            self, 
            "Confirm Clear", 
            "Are you sure you want to clear all assignments?\nThis will remove all unscheduled assignments.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            self.assignments = []
            self.update_display()
            self.statusBar().showMessage("All assignments cleared")
            self.save_data()
    
    def clear_time_slots(self):
        """Clear all time slots"""
        if not self.time_slots:
            return
        
        # Check if any assignments are scheduled
        if self.scheduled_assignments:
            warning = QMessageBox.warning(
                self,
                "Assignments Scheduled",
                "You have assignments scheduled using these time slots. Clearing all time slots will also clear your schedule.\n\nDo you want to continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if warning != QMessageBox.Yes:
                return
                
            # Clear scheduled assignments too
            self.scheduled_assignments = []
        
        confirm = QMessageBox.question(
            self, 
            "Confirm Clear", 
            "Are you sure you want to clear all time slots?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            self.time_slots = []
            self.update_display()
            self.statusBar().showMessage("All time slots cleared")
            self.save_data()
    
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
