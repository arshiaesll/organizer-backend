from datetime import datetime, timedelta
from typing import List
import uuid
class Assignment:
    def __init__(self, name: str, due_date: datetime, expected_completion_time: timedelta, completed: bool = False):
        self.name = name
        self.due_date = due_date
        self.expected_completion_time = expected_completion_time
        self.completed = completed

class ScheduledAssignment(Assignment):
    def __init__(self, name: str, due_date: datetime, expected_completion_time: timedelta, assigned_date: datetime):
        super().__init__(name, due_date, expected_completion_time)
        self.assigned_date = assigned_date

class TimeSlot:
    def __init__(self, start: datetime, duration: timedelta):
        self.start = start
        self.duration = duration
        self.id = uuid.uuid4()

class UserPreferences:
    def __init__(self, min_study_length: timedelta, max_study_length: timedelta, 
                 min_break_length: timedelta, max_break_length: timedelta):
        self.min_study_length = min_study_length
        self.max_study_length = max_study_length
        self.min_break_length = min_break_length
        self.max_break_length = max_break_length



if __name__ == "__main__":
    # Create some example dates and times
    now = datetime.now()  # Current date and time
    tomorrow = now + timedelta(days=1)  # Add 1 day
    next_week = now + timedelta(weeks=1)  # Add 1 week
    
    # Create an assignment due next week that takes 2 hours to complete
    assignment1 = Assignment(
        name="Math Homework",
        due_date=next_week,
        expected_completion_time=timedelta(hours=2)
    )
    print(f"Assignment '{assignment1.name}' is due on {assignment1.due_date.strftime('%Y-%m-%d %H:%M')}")
    print(f"Expected completion time: {assignment1.expected_completion_time}")

    # Create a scheduled assignment for tomorrow that takes 1.5 hours
    scheduled_assignment = ScheduledAssignment(
        name="Physics Lab",
        due_date=next_week,
        expected_completion_time=timedelta(hours=1, minutes=30),
        assigned_date=tomorrow
    )
    print(f"\nScheduled Assignment '{scheduled_assignment.name}':")
    print(f"Scheduled for: {scheduled_assignment.assigned_date.strftime('%Y-%m-%d %H:%M')}")
    print(f"Due date: {scheduled_assignment.due_date.strftime('%Y-%m-%d %H:%M')}")

    # Create a time slot for studying today
    study_slot = TimeSlot(
        start=now.replace(hour=14, minute=0),  # Today at 2:00 PM
        duration=timedelta(minutes=45)
    )
    print(f"\nStudy slot starts at: {study_slot.start.strftime('%Y-%m-%d %H:%M')}")
    print(f"Duration: {study_slot.duration}")

    # Example of user preferences with various time intervals
    preferences = UserPreferences(
        min_study_length=timedelta(minutes=30),
        max_study_length=timedelta(hours=2),
        min_break_length=timedelta(minutes=5),
        max_break_length=timedelta(minutes=15)
    )
    print(f"\nUser Preferences:")
    print(f"Minimum study time: {preferences.min_study_length}")
    print(f"Maximum study time: {preferences.max_study_length}")
    pass