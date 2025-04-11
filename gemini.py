import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
from typing import List
from organizer import Assignment, ScheduledAssignment, TimeSlot, UserPreferences
from datetime import datetime, timedelta, timezone
from prompts import RESPONSE_SCHEMA

# Load environment variables
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv()
load_dotenv(ENV_PATH)

# Configure Gemini
genai.configure(api_key=os.getenv("GENAI_API_KEY"))

# Initialize the model
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash"
)

def schedule_assignments(assignments: List[Assignment], available_time_slots: List[TimeSlot], user_preferences: UserPreferences):
    """
    Ask Gemini model to schedule unscheduled assignments into available time slots
    based on user preferences.
    """
    # Format assignments for the prompt
    assignments_data = []
    for a in assignments:
        completion_time_seconds = int(a.expected_completion_time.total_seconds())
        assignments_data.append({
            "name": a.name,
            "due_date": a.due_date.isoformat(),
            "expected_completion_time": completion_time_seconds
        })
    
    # Format time slots for the prompt
    time_slots_data = []
    for ts in available_time_slots:
        duration_seconds = int(ts.duration.total_seconds())
        time_slots_data.append({
            "start": ts.start.isoformat(),
            "duration": duration_seconds,
            "id": str(ts.id)
        })
    
    # Format user preferences
    preferences_data = {
        "min_study_length": int(user_preferences.min_study_length.total_seconds()),
        "max_study_length": int(user_preferences.max_study_length.total_seconds()),
        "break_length": int(user_preferences.min_break_length.total_seconds())
    }
    
    # Construct the prompt
    prompt = f"""
    I need help scheduling my assignments into available time slots.
    
    Current time: {datetime.now().isoformat()}
    
    Unscheduled assignments: {json.dumps(assignments_data, indent=2)}
    
    Available time slots: {json.dumps(time_slots_data, indent=2)}
    
    My preferences: {json.dumps(preferences_data, indent=2)}
    
    Please assign each assignment to appropriate time slots based on due dates, 
    estimated completion times, and my preferences.
    
    IMPORTANT INSTRUCTIONS:
    1. CRITICAL: Each study session MUST be at least {user_preferences.min_study_length.total_seconds()} seconds ({format_duration(user_preferences.min_study_length)}) long.
       - Even if an assignment takes less time than this, you MUST still schedule it for at least {user_preferences.min_study_length.total_seconds()} seconds.
       - For example, if an assignment takes only 20 minutes but the minimum study length is 30 minutes, schedule it for 30 minutes.
    
    2. CRITICAL: Each study session MUST NOT exceed {user_preferences.max_study_length.total_seconds()} seconds ({format_duration(user_preferences.max_study_length)}).
       - If an assignment's expected completion time exceeds this limit, you MUST split it into multiple sessions.
       - When splitting assignments, each session MUST be at least {user_preferences.min_study_length.total_seconds()} seconds ({format_duration(user_preferences.min_study_length)}).
       - NEVER create sessions shorter than {user_preferences.min_study_length.total_seconds()} seconds, even for the last session of a split assignment.
    
    3. For each session, specify the start time and duration in seconds.
       - The duration MUST be between {user_preferences.min_study_length.total_seconds()} and {user_preferences.max_study_length.total_seconds()} seconds.
       - This is a strict requirement enforced by the response schema.
    
    4. Number the sessions sequentially (1, 2, 3, etc.) for each assignment.
    
    5. Try to schedule sessions for the same assignment on consecutive days when possible.
    
    6. IMPORTANT: Always include breaks between study sessions. Never schedule back-to-back study sessions.
       - After each study session, take a break of {user_preferences.min_break_length.total_seconds()} seconds ({format_duration(user_preferences.min_break_length)}).
       - For example, if you schedule a session at 10:00 AM, the next session should not start until at least {user_preferences.min_break_length.total_seconds()} seconds after the previous session ends.
    
    7. CRITICAL: You MUST ONLY schedule sessions within the available time slots provided above.
       - Do NOT create new time slots or suggest times outside the available slots.
       - If there aren't enough time slots to schedule all assignments, prioritize based on due dates.
    
    8. MOST IMPORTANT: You MUST schedule ALL assignments provided in the list.
       - Every single assignment in the "Unscheduled assignments" list must have at least one session scheduled.
    
    9. DOUBLE-CHECK: Before submitting your response, verify that:
       - Every session is at least {user_preferences.min_study_length.total_seconds()} seconds ({format_duration(user_preferences.min_study_length)})
       - No session exceeds {user_preferences.max_study_length.total_seconds()} seconds ({format_duration(user_preferences.max_study_length)})
       - All sessions are within the available time slots
       - All assignments have at least one session scheduled
       - When splitting assignments, all sessions (including the last one) meet the minimum study length
    
    Respond with a JSON object containing a key 'newly_scheduled_assignments' that maps assignments to time slots.
    Each assignment should include its name, due date, expected completion time, and a list of sessions.
    """
    
    # Generate response from Gemini with schema
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA
        )
    )
    
    return response.text


def create_scheduled_assignments(gemini_response: str, assignments: List[Assignment]) -> List[ScheduledAssignment]:
    """
    Parse Gemini API response and create a list of ScheduledAssignment objects.
    """
    # Create lookup dictionary for assignments
    assignment_dict = {a.name: a for a in assignments}
    
    # Parse the JSON response
    response_data = json.loads(gemini_response)
    scheduled_assignments = []
    
    # Process each scheduled assignment in the response
    for item in response_data.get('newly_scheduled_assignments', []):
        # Get assignment details
        assignment_name = item.get('assignment_name')
        sessions = item.get('sessions', [])
        
        # Find the original assignment by name
        original_assignment = assignment_dict.get(assignment_name)
        if not original_assignment:
            continue
        
        # Create a scheduled assignment for each session
        for session in sessions:
            # Parse the datetime string, handling 'Z' timezone indicator
            start_time_str = session.get('start_time')
            if start_time_str.endswith('Z'):
                # Remove 'Z' and parse as UTC
                start_time_str = start_time_str[:-1]
                start_time = datetime.fromisoformat(start_time_str).replace(tzinfo=timezone.utc)
            else:
                start_time = datetime.fromisoformat(start_time_str)
            
            # Get session duration in seconds
            session_duration_seconds = session.get('duration', 0)
            session_duration = timedelta(seconds=session_duration_seconds)
            
            # Get session number
            session_number = session.get('session_number', 1)
            
            # Create a new scheduled assignment
            scheduled_assignment = ScheduledAssignment(
                name=original_assignment.name,
                due_date=original_assignment.due_date,
                expected_completion_time=original_assignment.expected_completion_time,
                assigned_date=start_time
            )
            
            # Add session information as attributes
            scheduled_assignment.session_duration = session_duration
            scheduled_assignment.session_number = session_number
            
            scheduled_assignments.append(scheduled_assignment)
    
    return scheduled_assignments


def format_duration(td: timedelta) -> str:
    """Format a timedelta as a human-readable duration string."""
    hours = td.seconds // 3600
    minutes = (td.seconds % 3600) // 60
    
    if hours > 0 and minutes > 0:
        return f"{hours} hour{'s' if hours != 1 else ''} and {minutes} minute{'s' if minutes != 1 else ''}"
    elif hours > 0:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    else:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"


if __name__ == "__main__":
    # Test example for the scheduling function
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    next_week = now + timedelta(days=7)
    
    # Create a more complicated set of assignments with varying durations and due dates
    assignments = [
        # Short assignments due soon
        Assignment("Math Quiz Prep", tomorrow + timedelta(days=1), timedelta(minutes=45)),
        Assignment("History Reading", tomorrow + timedelta(days=2), timedelta(minutes=30)),
        
        # Medium assignments due in a few days
        Assignment("Physics Lab Report", tomorrow + timedelta(days=3), timedelta(hours=1, minutes=15)),
        Assignment("Chemistry Homework", tomorrow + timedelta(days=4), timedelta(hours=1)),
        
        # Longer assignments due next week
        Assignment("Research Paper", next_week, timedelta(hours=3)),
        Assignment("Computer Science Project", next_week - timedelta(days=1), timedelta(hours=2, minutes=30)),
        Assignment("Literature Essay", next_week + timedelta(days=1), timedelta(hours=2)),
        
        # Very short assignments
        Assignment("Spanish Vocabulary", tomorrow, timedelta(minutes=20)),
        Assignment("Biology Notes Review", tomorrow + timedelta(days=1), timedelta(minutes=25))
    ]
    
    # Create a more complicated set of time slots with varying durations and times
    time_slots = [
        # Morning slots
        TimeSlot(tomorrow.replace(hour=8, minute=0), timedelta(hours=1)),
        TimeSlot(tomorrow.replace(hour=9, minute=30), timedelta(hours=1, minutes=30)),
        
        # Afternoon slots
        TimeSlot(tomorrow.replace(hour=14, minute=0), timedelta(hours=2)),
        TimeSlot(tomorrow.replace(hour=16, minute=30), timedelta(hours=1)),
        
        # Evening slots
        TimeSlot(tomorrow.replace(hour=19, minute=0), timedelta(hours=1, minutes=30)),
        
        # Next day slots
        TimeSlot((tomorrow + timedelta(days=1)).replace(hour=10, minute=0), timedelta(hours=2)),
        TimeSlot((tomorrow + timedelta(days=1)).replace(hour=13, minute=0), timedelta(hours=1)),
        TimeSlot((tomorrow + timedelta(days=1)).replace(hour=15, minute=0), timedelta(hours=1, minutes=30)),
        
        # Day 3 slots
        TimeSlot((tomorrow + timedelta(days=2)).replace(hour=9, minute=0), timedelta(hours=1)),
        TimeSlot((tomorrow + timedelta(days=2)).replace(hour=11, minute=0), timedelta(hours=2)),
        TimeSlot((tomorrow + timedelta(days=2)).replace(hour=14, minute=0), timedelta(hours=1)),
        
        # Day 4 slots
        TimeSlot((tomorrow + timedelta(days=3)).replace(hour=10, minute=0), timedelta(hours=1, minutes=30)),
        TimeSlot((tomorrow + timedelta(days=3)).replace(hour=12, minute=30), timedelta(hours=1)),
        
        # Day 5 slots (weekend)
        TimeSlot((tomorrow + timedelta(days=4)).replace(hour=9, minute=0), timedelta(hours=3)),
        TimeSlot((tomorrow + timedelta(days=4)).replace(hour=13, minute=0), timedelta(hours=2)),
        
        # Day 6 slots (weekend)
        TimeSlot((tomorrow + timedelta(days=5)).replace(hour=10, minute=0), timedelta(hours=2, minutes=30)),
        TimeSlot((tomorrow + timedelta(days=5)).replace(hour=15, minute=0), timedelta(hours=1, minutes=30))
    ]
    
    # User preferences
    preferences = UserPreferences(
        min_study_length=timedelta(minutes=30),
        max_study_length=timedelta(hours=1.5),
        min_break_length=timedelta(minutes=15),
        max_break_length=timedelta(minutes=15)
    )
    
    # Test the scheduling function
    result = schedule_assignments(assignments, time_slots, preferences)
    print(json.dumps(json.loads(result), indent=2))
    
    # Print available time slots in a nice format
    print("\n=== AVAILABLE TIME SLOTS ===")
    for i, ts in enumerate(time_slots, 1):
        # Format the start time in a readable way
        start_time_str = ts.start.strftime("%A, %B %d, %Y at %I:%M %p")
        
        # Format duration string
        duration_str = format_duration(ts.duration)
        
        print(f"\n⏰ Time Slot {i}")
        print(f"   📅 Available: {start_time_str}")
        print(f"   ⏱️  Duration: {duration_str}")
        print(f"   {'─' * 50}")
    
    # Test creating scheduled assignments from the response
    scheduled_assignments = create_scheduled_assignments(result, assignments)
    
    # Print in a more human-readable format
    print("\n=== SCHEDULED ASSIGNMENTS ===")
    for sa in scheduled_assignments:
        # Format the assigned date and due date in a more readable way
        assigned_date_str = sa.assigned_date.strftime("%A, %B %d, %Y at %I:%M %p")
        due_date_str = sa.due_date.strftime("%A, %B %d, %Y")
        
        # Get session duration in hours and minutes
        session_duration = getattr(sa, 'session_duration', sa.expected_completion_time)
        duration_str = format_duration(session_duration)
        
        # Get session number if available
        session_number = getattr(sa, 'session_number', 1)
        session_info = f" (Session {session_number})" if session_number > 1 else ""
        
        print(f"\n📚 {sa.name}{session_info}")
        print(f"   📅 Scheduled for: {assigned_date_str}")
        print(f"   ⏱️  Session Duration: {duration_str}")
        print(f"   📌 Due by: {due_date_str}")
        print(f"   {'─' * 50}")
    
    # Generate metadata for all platforms
    # youtube_metadata = generate_youtube_metadata(video_description)
    

