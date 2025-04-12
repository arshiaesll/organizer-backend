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
    QGridLayout, QDialog, QGroupBox, QSizePolicy, QSpacerItem
)
from PySide6.QtCore import Qt, QDateTime, QDate, QTime, QSize
from PySide6.QtGui import QColor, QPalette, QFont

from organizer import Assignment, ScheduledAssignment, TimeSlot, UserPreferences
from gemini import schedule_assignments, create_scheduled_assignments, format_duration
from styles import (
    NORMAL_BUTTON_STYLE, WARNING_BUTTON_STYLE, DANGER_BUTTON_STYLE, SUCCESS_BUTTON_STYLE,
    NAV_BUTTON_STYLE, TODAY_BUTTON_STYLE, DIALOG_BUTTON_STYLE, 
    get_simple_button_style, get_colored_button_style,
    SCHEDULED_BG_COLOR, UNSCHEDULED_BG_COLOR, TIME_SLOT_BG_COLOR
)


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
        self.name_label.setFont(QFont("Arial", 9, QFont.Bold))
        self.name_label.setStyleSheet("color: black;")
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignCenter)
        
        self.time_label = QLabel(f"⏰ {time_str}")
        self.time_label.setFont(QFont("Arial", 8))
        self.time_label.setStyleSheet("color: black;")
        
        self.duration_label = QLabel(f"⏱️ {format_duration(session_duration)}")
        self.duration_label.setFont(QFont("Arial", 8))
        self.duration_label.setStyleSheet("color: black;")
        
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
        layout.addStretch()
    
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
            multi_hour_layout = QVBoxLayout(self.multi_hour_widget)
            multi_hour_layout.setContentsMargins(0, 0, 0, 0)
            multi_hour_layout.setSpacing(0)
            
            # Ensure the multi-hour widget is properly sized and stays on top
            self.multi_hour_widget.raise_()
            
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
            
            # Store total_height as an instance variable for resizeEvent
            self.hourly_total_height = total_height
            
            # Define resize event for hourly widget
            def resize_multi_hour_widget(event):
                """Handle resizing of the hourly widget to keep multi-hour assignments properly positioned"""
                # First update the multi-hour widget's width to match the parent
                width = self.hourly_widget.width()
                self.multi_hour_widget.setGeometry(0, 0, width, self.hourly_total_height)
                
                # Adjust all child frames in the multi-hour widget
                for child in self.multi_hour_widget.findChildren(QFrame):
                    current_geometry = child.geometry()
                    child.setGeometry(10, current_geometry.y(), width - 20, current_geometry.height())
                
                # Call the original resize event
                QWidget.resizeEvent(self.hourly_widget, event)
            
            self.hourly_widget.resizeEvent = resize_multi_hour_widget
            
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
        # Make sure we're using naive datetime for comparison
        assigned_date = scheduled_assignment.assigned_date
        if assigned_date.tzinfo is not None:
            scheduled_assignment.assigned_date = assigned_date.replace(tzinfo=None)
            assigned_date = scheduled_assignment.assigned_date
        
        print(f"DayWidget: Adding assignment {scheduled_assignment.name} at {assigned_date} to day {self.date.date()}")
        
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
                print(f"Creating multi-hour container for {scheduled_assignment.name}")
                container.setFrameStyle(QFrame.Box | QFrame.Raised)
                container.setLineWidth(1)
                container.setStyleSheet(f"background-color: {color}; border-radius: 5px;")
                
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
                    
                    # Ensure minimum height and set absolute position
                    container.setFixedHeight(max(50, int(pixel_height)))  # Minimum height of 50px
                    container.setGeometry(10, int(y_position), self.hourly_widget.width() - 20, int(pixel_height))
                    
                    # Make sure the container is visible
                    container.show()
                    print(f"Multi-hour container positioned at y={y_position}, height={pixel_height}")
                    
                    # Ensure it stays on top
                    container.raise_()
                    
                    # Force layout update
                    self.multi_hour_widget.updateGeometry()
            else:
                # For single-hour items, add to the regular hour layout
                # Find the correct hour to place this in
                target_hour = max(6, min(22, start_hour))
                hour_info = self.hours.get(target_hour)
                
                if hour_info:
                    item = ScheduledAssignmentItem(scheduled_assignment, color_manager)
                    hour_info['layout'].addWidget(item)
                    print(f"Added single-hour item for {scheduled_assignment.name} to hour {target_hour}")
        else:
            # Simple list view - add normally
            item = ScheduledAssignmentItem(scheduled_assignment, color_manager)
            self.list_layout.addWidget(item)
            print(f"Added assignment {scheduled_assignment.name} to simple list view")
    
    def add_time_slot(self, time_slot: TimeSlot):
        """Add a time slot to this day - only highlights the hour blocks that contain the time slot"""
        self.time_slots.append(time_slot)
        
        if self.show_hourly:
            # Get the start time and duration
            start_time = time_slot.start
            duration = time_slot.duration
            
            # Calculate duration in hours (rounded down to integer)
            duration_hours = int(duration.total_seconds() // 3600)
            
            # Create a list of hour blocks to highlight - exactly match the duration hours
            hours_to_highlight = []
            for i in range(duration_hours):
                hour = start_time.hour + i
                if 6 <= hour < 23:  # Only highlight visible hours
                    hours_to_highlight.append(hour)
            
            print(f"Time slot from {start_time}, duration: {duration_hours} hours")
            print(f"Highlighting hours: {hours_to_highlight}")
            
            # Highlight each hour block in our calculated list
            for hour in hours_to_highlight:
                hour_info = self.hours.get(hour)
                if hour_info:
                    # Check if there's an assignment already scheduled for this hour
                    hour_has_assignment = False
                    
                    for assignment in self.scheduled_assignments:
                        assignment_hour = assignment.assigned_date.hour
                        assignment_duration = getattr(assignment, 'session_duration', assignment.expected_completion_time)
                        assignment_end_hour = (assignment.assigned_date + assignment_duration).hour
                        
                        # If assignment spans this hour, consider the hour occupied
                        if assignment_hour <= hour <= assignment_end_hour:
                            hour_has_assignment = True
                            break
                    
                    # Only highlight if there's no assignment in this hour
                    if not hour_has_assignment:
                        # Change the background color of the hour frame to indicate a time slot
                        hour_info['frame'].setStyleSheet(f"background-color: {TIME_SLOT_BG_COLOR};")  # Light green with transparency
                        
                        # Add a tooltip to show the time slot info
                        slot_time = start_time.strftime("%I:%M %p")
                        slot_duration = format_duration(duration)
                        hour_info['frame'].setToolTip(f"Available Time Slot: {slot_time}, Duration: {slot_duration}")
                    
                    # Store the time slot reference to allow editing (even if not highlighted)
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
            if self.multi_hour_widget and self.multi_hour_widget.layout():
                print("Clearing multi-hour widget")
                while self.multi_hour_widget.layout().count():
                    item = self.multi_hour_widget.layout().takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                        
                # Also check for any directly added children
                for child in self.multi_hour_widget.findChildren(QFrame):
                    print(f"Removing child frame from multi-hour widget: {child}")
                    child.setParent(None)
                    child.deleteLater()
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
    
    def __init__(self, parent=None, on_edit_slot=None, on_delete_slot=None, color_manager: ColorManager = None):
        super().__init__(parent)
        self.color_manager = color_manager or ColorManager()
        self.on_edit_slot = on_edit_slot
        self.on_delete_slot = on_delete_slot
        self.current_week_start = self.get_current_week_start()
        self.days = {}  # Will store day widgets by date
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
        self.prev_week_btn.setStyleSheet(NAV_BUTTON_STYLE)
        
        self.today_btn = QPushButton("Today")
        self.today_btn.clicked.connect(self.show_current_week)
        self.today_btn.setStyleSheet(TODAY_BUTTON_STYLE)
        
        self.next_week_btn = QPushButton("Next Week ▶")
        self.next_week_btn.clicked.connect(self.show_next_week)
        self.next_week_btn.setStyleSheet(NAV_BUTTON_STYLE)
        
        self.week_label = QLabel()
        self.week_label.setAlignment(Qt.AlignCenter)
        self.week_label.setFont(QFont("Arial", 12, QFont.Bold))
        
        nav_layout.addWidget(self.prev_week_btn)
        nav_layout.addWidget(self.today_btn)
        nav_layout.addWidget(self.week_label)
        nav_layout.addWidget(self.next_week_btn)
        
        layout.addLayout(nav_layout)
        
        # Calendar grid - simple grid without headers
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(6)
        
        # Add grid to main layout
        layout.addLayout(self.grid_layout)
        
        # Create the calendar days (1 week)
        self.create_day_widgets()
    
    def create_day_widgets(self):
        """Create the day widgets for the current week"""
        for day in range(7):
            current_date = self.current_week_start + timedelta(days=day)
            day_widget = DayWidget(
                current_date,
                on_edit_slot=self.on_edit_slot,
                on_delete_slot=self.on_delete_slot,
                show_hourly=True  # Enable hourly view
            )
            self.grid_layout.addWidget(day_widget, 0, day)
            self.days[current_date.date()] = day_widget
            
            # Make column sizes even
            self.grid_layout.setColumnMinimumWidth(day, 200)
        
        # Update the week label
        self.update_week_label()
        
        # Refresh the display if we have data
        self.update_display()
    
    def update_week_label(self):
        """Update the week label with the current week range"""
        week_end = self.current_week_start + timedelta(days=6)
        self.week_label.setText(
            f"{self.current_week_start.strftime('%B %d')} - {week_end.strftime('%B %d, %Y')}"
        )
    
    def update_day_widgets(self):
        """Update the existing day widgets with new dates"""
        # First clear the days mapping
        old_days = self.days.copy()
        self.days = {}
        
        for day in range(7):
            current_date = self.current_week_start + timedelta(days=day)
            current_day = current_date.date()
            
            # Get the day widget at this position
            day_widget = self.grid_layout.itemAtPosition(0, day).widget()
            
            # Update its date
            day_widget.date = current_date
            day_widget.header.setText(current_date.strftime("%a, %b %d"))
            
            # Highlight today
            today = datetime.now().date()
            if current_day == today:
                day_widget.setStyleSheet("background-color: #f0f8ff;")  # Light blue for today
            elif current_day.weekday() >= 5:  # Weekend
                day_widget.setStyleSheet("background-color: #f5f5f5;")  # Light grey for weekend
            else:
                day_widget.setStyleSheet("")  # Clear any previous styling
            
            # Clear the day widget
            day_widget.clear_all()
            
            # Reset internal lists to ensure no leftover assignments or time slots
            day_widget.scheduled_assignments = []
            day_widget.time_slots = []
            
            # Update the dates mapping
            self.days[current_day] = day_widget
        
        # Update the week label
        self.update_week_label()
        
        # Refresh the display
        self.update_display()
    
    def update_display(self):
        """Update the display with current assignments and time slots"""
        # Clear all widgets first
        for day_widget in self.days.values():
            day_widget.clear_all()
        
        # First add time slots
        self.display_time_slots(getattr(self, '_time_slots', []))
        
        # Then add scheduled assignments on top
        self.display_scheduled_assignments(getattr(self, '_scheduled_assignments', []))
    
    def show_previous_week(self):
        """Show the previous week"""
        self.current_week_start -= timedelta(days=7)
        self.update_day_widgets()
    
    def show_next_week(self):
        """Show the next week"""
        self.current_week_start += timedelta(days=7)
        self.update_day_widgets()
    
    def show_current_week(self):
        """Show the current week"""
        self.current_week_start = self.get_current_week_start()
        self.update_day_widgets()
    
    def display_scheduled_assignments(self, scheduled_assignments: List[ScheduledAssignment]):
        """Display scheduled assignments on the calendar"""
        self._scheduled_assignments = scheduled_assignments
        
        # Debug output
        print(f"CalendarView: Displaying {len(scheduled_assignments)} scheduled assignments")
        
        # Get the date range for the current view
        start_date = self.current_week_start.date()
        end_date = (self.current_week_start + timedelta(days=6)).date()
        print(f"Current week range: {start_date} to {end_date}")
        
        # Clear all existing assignments first
        for day_widget in self.days.values():
            day_widget.clear_scheduled_assignments()
        
        # Add new assignments
        for assignment in scheduled_assignments:
            # Make sure we're using naive datetime to avoid timezone issues
            assigned_date = assignment.assigned_date
            if assigned_date.tzinfo is not None:
                assigned_date = assigned_date.replace(tzinfo=None)
                assignment.assigned_date = assigned_date
            
            # Get the date and ensure it's a naive datetime for comparison
            date = assigned_date.date()
            
            # Only display assignments in the current week view
            if start_date <= date <= end_date:
                print(f"Assignment: {assignment.name} at {assigned_date} (Date: {date})")
                
                if date in self.days:
                    print(f"Adding assignment to day {date}")
                    self.days[date].add_scheduled_assignment(assignment, self.color_manager)
                else:
                    print(f"No day widget found for date {date}")
    
    def display_time_slots(self, time_slots: List[TimeSlot]):
        """Display time slots on the calendar"""
        self._time_slots = time_slots
        
        # Debug output
        print(f"CalendarView: Displaying {len(time_slots)} time slots")
        
        # Get the date range for the current view
        start_date = self.current_week_start.date()
        end_date = (self.current_week_start + timedelta(days=6)).date()
        
        # Clear any existing time slots
        for day_widget in self.days.values():
            day_widget.clear_time_slots()
        
        # Add new time slots, but only if they're in the current week
        for slot in time_slots:
            date = slot.start.date()
            
            # Only display time slots in the current week view
            if start_date <= date <= end_date:
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
    """Dialog for adding or editing an assignment"""
    
    def __init__(self, parent=None, assignment=None):
        super().__init__(parent)
        self.editing = assignment is not None
        self.original_assignment = assignment
        self.setWindowTitle("Edit Assignment" if self.editing else "Add Assignment")
        self.setup_ui()
        
        # Fill fields if editing
        if self.editing:
            self.name_edit.setText(assignment.name)
            self.due_date_edit.setDateTime(QDateTime(assignment.due_date))
            
            # Set hours and minutes
            hours = int(assignment.expected_completion_time.total_seconds() // 3600)
            minutes = int((assignment.expected_completion_time.total_seconds() % 3600) // 60)
            self.hours_spin.setValue(hours)
            self.minutes_spin.setValue(minutes)
    
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
        
        # Button layout
        button_layout = QHBoxLayout()
        
        # Add/Save button
        self.action_button = QPushButton("Save" if self.editing else "Add")
        self.action_button.clicked.connect(self.accept)
        self.action_button.setStyleSheet(DIALOG_BUTTON_STYLE)
        
        # Cancel button (only for edit mode)
        if self.editing:
            self.cancel_button = QPushButton("Cancel")
            self.cancel_button.clicked.connect(self.reject)
            self.cancel_button.setStyleSheet(get_simple_button_style("#9E9E9E"))  # Gray
            button_layout.addWidget(self.cancel_button)
        
        button_layout.addWidget(self.action_button)
        layout.addRow("", button_layout)
    
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
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.accept)
        self.add_button.setStyleSheet(DIALOG_BUTTON_STYLE)
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
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.accept)
        self.save_button.setStyleSheet(DIALOG_BUTTON_STYLE)
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


class AssignmentListDialog(QDialog):
    """Dialog to view all assignments"""
    
    def __init__(self, assignments, scheduled_assignments, parent=None, on_edit=None):
        super().__init__(parent)
        self.assignments = assignments
        self.scheduled_assignments = scheduled_assignments
        self.on_edit = on_edit
        self.setWindowTitle("All Assignments")
        self.resize(500, 600)
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface"""
        layout = QVBoxLayout(self)
        
        # Create a scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        # Create a widget to hold the assignments
        scroll_content = QWidget()
        self.assignments_layout = QVBoxLayout(scroll_content)
        
        # Add assignments
        if not self.assignments:
            no_assignments = QLabel("No assignments added yet")
            no_assignments.setAlignment(Qt.AlignCenter)
            self.assignments_layout.addWidget(no_assignments)
        else:
            # Sort assignments by due date
            sorted_assignments = sorted(self.assignments, key=lambda a: a.due_date)
            
            for assignment in sorted_assignments:
                # Check if this assignment is scheduled
                is_scheduled = any(sa.name == assignment.name for sa in self.scheduled_assignments)
                
                # Create a frame for the assignment
                frame = QFrame()
                frame.setFrameShape(QFrame.StyledPanel)
                frame.setLineWidth(1)
                frame_layout = QVBoxLayout(frame)
                
                # Create header layout with title and edit button
                header_layout = QHBoxLayout()
                
                # Title
                title_label = QLabel(f"<b>{assignment.name}</b>")
                title_label.setStyleSheet("font-size: 16px;")
                header_layout.addWidget(title_label)
                
                # Add spacer to push edit button to the right
                header_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
                
                # Edit button
                if self.on_edit:
                    edit_button = QPushButton("Edit")
                    edit_button.setStyleSheet(get_simple_button_style("#2196F3"))  # Blue
                    edit_button.setMaximumWidth(60)
                    edit_button.clicked.connect(lambda checked, a=assignment: self.on_edit(a))
                    header_layout.addWidget(edit_button)
                
                frame_layout.addLayout(header_layout)
                
                # Add due date
                due_date = QLabel(f"Due: {assignment.due_date.strftime('%Y-%m-%d %H:%M')}")
                frame_layout.addWidget(due_date)
                
                # Add expected completion time
                hours = int(assignment.expected_completion_time.total_seconds() // 3600)
                minutes = int((assignment.expected_completion_time.total_seconds() % 3600) // 60)
                
                time_text = ""
                if hours > 0:
                    time_text += f"{hours} hour{'s' if hours != 1 else ''}"
                if minutes > 0:
                    if time_text:
                        time_text += " "
                    time_text += f"{minutes} minute{'s' if minutes != 1 else ''}"
                
                expected_time = QLabel(f"Expected Time: {time_text}")
                frame_layout.addWidget(expected_time)
                
                # Add status
                status_label = QLabel(f"Status: {'Scheduled' if is_scheduled else 'Not Scheduled'}")
                status_label.setStyleSheet(f"color: {'#4CAF50' if is_scheduled else '#F44336'}")
                frame_layout.addWidget(status_label)
                
                self.assignments_layout.addWidget(frame)
        
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        
        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setStyleSheet(DIALOG_BUTTON_STYLE)
        close_button.setMaximumWidth(120)
        
        btn_layout = QHBoxLayout()
        btn_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        btn_layout.addWidget(close_button)
        btn_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        layout.addLayout(btn_layout)


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
        
        # Create a global color manager to ensure consistent colors
        self.color_manager = ColorManager()
        
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
        
        self.add_assignment_button = QPushButton("Add")
        self.add_assignment_button.clicked.connect(self.add_assignment)
        self.add_assignment_button.setStyleSheet(NORMAL_BUTTON_STYLE)
        
        self.view_assignments_button = QPushButton("View")
        self.view_assignments_button.clicked.connect(self.view_assignments)
        self.view_assignments_button.setStyleSheet(NORMAL_BUTTON_STYLE)
        
        self.clear_assignments_button = QPushButton("Clear")
        self.clear_assignments_button.clicked.connect(self.clear_assignments)
        self.clear_assignments_button.setStyleSheet(WARNING_BUTTON_STYLE)
        
        assignment_layout.addWidget(self.add_assignment_button)
        assignment_layout.addWidget(self.view_assignments_button)
        assignment_layout.addWidget(self.clear_assignments_button)
        
        # Time slots controls group
        timeslot_group = QGroupBox("Time Slots")
        timeslot_layout = QHBoxLayout(timeslot_group)
        
        self.add_time_slot_button = QPushButton("Add")
        self.add_time_slot_button.clicked.connect(self.add_time_slot)
        self.add_time_slot_button.setStyleSheet(NORMAL_BUTTON_STYLE)
        
        self.clear_time_slots_button = QPushButton("Clear")
        self.clear_time_slots_button.clicked.connect(self.clear_time_slots)
        self.clear_time_slots_button.setStyleSheet(WARNING_BUTTON_STYLE)
        
        timeslot_layout.addWidget(self.add_time_slot_button)
        timeslot_layout.addWidget(self.clear_time_slots_button)
        
        # Scheduling controls group
        schedule_group = QGroupBox("Scheduling")
        schedule_layout = QHBoxLayout(schedule_group)
        
        self.preferences_button = QPushButton("Preferences")
        self.preferences_button.clicked.connect(self.edit_preferences)
        self.preferences_button.setStyleSheet(NORMAL_BUTTON_STYLE)
        
        self.schedule_button = QPushButton("Schedule")
        self.schedule_button.clicked.connect(self.schedule_assignments)
        self.schedule_button.setStyleSheet(SUCCESS_BUTTON_STYLE)
        
        self.reset_schedule_button = QPushButton("Reset")
        self.reset_schedule_button.clicked.connect(self.reset_schedule)
        self.reset_schedule_button.setStyleSheet(DANGER_BUTTON_STYLE)
        
        schedule_layout.addWidget(self.preferences_button)
        schedule_layout.addWidget(self.schedule_button)
        schedule_layout.addWidget(self.reset_schedule_button)
        
        # Add control groups to main controls layout
        controls_layout.addWidget(assignment_group)
        controls_layout.addWidget(timeslot_group)
        controls_layout.addWidget(schedule_group)
        
        # Calendar view - pass the global color manager
        self.calendar_view = CalendarView(
            on_edit_slot=self.edit_assignment,
            on_delete_slot=self.delete_assignment,
            color_manager=self.color_manager
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
            
        print(f"Deserializing assignment: {data['name']} with assigned_date: {assigned_date}")
        
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
            
            # Make sure to preserve scheduled assignments while updating display
            self.update_display()
            self.save_data()
    
    def add_time_slot(self):
        """Add a new time slot"""
        dialog = TimeSlotDialog(self)
        if dialog.exec_():
            time_slot = dialog.get_time_slot()
            self.time_slots.append(time_slot)
            self.statusBar().showMessage(f"Added time slot: {time_slot.start.strftime('%Y-%m-%d %H:%M')}")
            
            # Make sure to preserve scheduled assignments while updating display
            self.update_display()
            self.save_data()
    
    def edit_assignment(self, assignment):
        """Edit an existing assignment"""
        # Check if this assignment is already scheduled
        is_scheduled = any(sa.name == assignment.name for sa in self.scheduled_assignments)
        
        if is_scheduled:
            warning = QMessageBox.warning(
                self,
                "Assignment Scheduled",
                "This assignment is already scheduled. Editing it may affect your schedule.\nDo you want to continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if warning != QMessageBox.Yes:
                return
        
        dialog = AssignmentDialog(self, assignment)
        if dialog.exec_():
            updated_assignment = dialog.get_assignment()
            
            # Get the original assignment name before updating (for scheduled assignment tracking)
            original_name = assignment.name
            
            # Find and replace the assignment
            for i, a in enumerate(self.assignments):
                if a is assignment:  # Same object
                    self.assignments[i] = updated_assignment
                    break
            
            # Update scheduled assignments if needed
            if is_scheduled:
                # Update name and expected completion time in scheduled assignments
                for sa in self.scheduled_assignments:
                    if sa.name == original_name:
                        sa.name = updated_assignment.name
                        sa.due_date = updated_assignment.due_date
                        sa.expected_completion_time = updated_assignment.expected_completion_time
            
            self.statusBar().showMessage(f"Updated assignment: {updated_assignment.name}")
            
            # Save immediately after editing
            self.save_data()
            
            # Then update the display
            self.update_display()
    
    def delete_assignment(self, assignment):
        """Delete an existing assignment"""
        # Remove the assignment from the list
        self.assignments = [a for a in self.assignments if a is not assignment]
        
        # Update scheduled assignments if needed
        self.scheduled_assignments = [sa for sa in self.scheduled_assignments if sa.name != assignment.name]
        
        self.statusBar().showMessage(f"Deleted assignment: {assignment.name}")
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
        if not self.assignments and not self.scheduled_assignments:
            return
            
        confirm = QMessageBox.question(
            self, 
            "Confirm Clear", 
            "Are you sure you want to clear all assignments?\nThis will remove all assignments including scheduled ones.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            self.assignments = []
            self.scheduled_assignments = []
            self.update_display()
            self.statusBar().showMessage("All assignments and schedules cleared")
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
    
    def reset_schedule(self):
        """Reset the schedule"""
        if not self.scheduled_assignments:
            return
            
        confirm = QMessageBox.question(
            self, 
            "Confirm Reset", 
            "Are you sure you want to reset the schedule?\nThis will remove all scheduled assignments but keep the assignments themselves.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            self.scheduled_assignments = []
            self.update_display()
            self.statusBar().showMessage("Schedule reset")
            self.save_data()
    
    def view_assignments(self):
        """Open a dialog to view all assignments"""
        dialog = AssignmentListDialog(self.assignments, self.scheduled_assignments, self, self.edit_assignment)
        result = dialog.exec_()
        
        # Refresh the UI after the dialog closes in case edits were made
        self.update_display()
        
    def update_display(self):
        """Update the calendar display"""
        print(f"MainWindow: Updating display with {len(self.time_slots)} time slots and {len(self.scheduled_assignments)} scheduled assignments")
        self.calendar_view.display_time_slots(self.time_slots)
        self.calendar_view.display_scheduled_assignments(self.scheduled_assignments)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
