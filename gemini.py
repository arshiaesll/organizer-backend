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
    model_name="gemini-2.0-flash",
    generation_config=genai.GenerationConfig(
        response_mime_type="application/json",
    )
)

def schedule_assignments(assignments: List[Assignment], available_time_slots: List[TimeSlot], user_preferences: UserPreferences):
    """
    Ask Gemini model to schedule unscheduled assignments into available time slots
    based on user preferences.
    """
    # Construct the prompt
    current_time = datetime.now()
    
    # Format assignments for the prompt
    assignments_data = []
    for a in assignments:
        # Convert timedelta to seconds
        completion_time_seconds = int(a.expected_completion_time.total_seconds())
        assignments_data.append({
            "name": a.name,
            "due_date": a.due_date.isoformat(),
            "expected_completion_time": completion_time_seconds
        })
    
    # Format time slots for the prompt
    time_slots_data = []
    for ts in available_time_slots:
        # Convert timedelta to seconds
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
        "min_break_length": int(user_preferences.min_break_length.total_seconds()),
        "max_break_length": int(user_preferences.max_break_length.total_seconds())
    }
    
    # Construct the prompt
    prompt = f"""
    I need help scheduling my assignments into available time slots.
    
    Current time: {current_time.isoformat()}
    
    Unscheduled assignments: {json.dumps(assignments_data, indent=2)}
    
    Available time slots: {json.dumps(time_slots_data, indent=2)}
    
    My preferences: {json.dumps(preferences_data, indent=2)}
    
    Please assign each assignment to appropriate time slots based on due dates, 
    estimated completion times, and my preferences.
    
    IMPORTANT INSTRUCTIONS:
    1. If an assignment's expected completion time exceeds my maximum study length ({user_preferences.max_study_length.total_seconds()} seconds), 
       split it into multiple sessions. Each session should be at least {user_preferences.min_study_length.total_seconds()} seconds long 
       but no longer than {user_preferences.max_study_length.total_seconds()} seconds.
    2. For each session, specify the start time and duration in seconds.
    3. Number the sessions sequentially (1, 2, 3, etc.) for each assignment.
    4. Try to schedule sessions for the same assignment on consecutive days when possible.
    5. IMPORTANT: Always include breaks between study sessions. Never schedule back-to-back study sessions.
       - After each study session, take a break of at least {user_preferences.min_break_length.total_seconds()} seconds.
       - Breaks should be between {user_preferences.min_break_length.total_seconds()} and {user_preferences.max_break_length.total_seconds()} seconds.
       - For example, if you schedule a session at 10:00 AM, the next session should not start until at least {user_preferences.min_break_length.total_seconds()} seconds after the previous session ends.
    
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
    
    # Parse and return the response
    return response.text

def create_scheduled_assignments(gemini_response: str, assignments: List[Assignment]) -> List[ScheduledAssignment]:
    """
    Parse Gemini API response and create a list of ScheduledAssignment objects.
    
    Args:
        gemini_response: JSON string returned from Gemini API
        assignments: Original list of unscheduled assignments
        
    Returns:
        List of ScheduledAssignment objects with session information
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


if __name__ == "__main__":
    # Test example for the scheduling function
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    next_week = now + timedelta(days=7)
    
    # Create sample assignments
    assignments = [
        Assignment("Math Homework", next_week, timedelta(hours=2)),
        Assignment("Physics Lab", next_week - timedelta(days=2), timedelta(hours=1, minutes=30)),
        Assignment("English Essay", next_week + timedelta(days=3), timedelta(hours=3))
    ]
    
    # Create sample time slots
    time_slots = [
        TimeSlot(tomorrow.replace(hour=14, minute=0), timedelta(hours=2)),
        TimeSlot(tomorrow.replace(hour=18, minute=0), timedelta(hours=1, minutes=30)),
        TimeSlot((tomorrow + timedelta(days=1)).replace(hour=10, minute=0), timedelta(hours=5))
    ]
    
    # User preferences
    preferences = UserPreferences(
        min_study_length=timedelta(minutes=30),
        max_study_length=timedelta(hours=1.5),
        min_break_length=timedelta(minutes=5),
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
        
        # Calculate duration in hours and minutes
        hours = ts.duration.seconds // 3600
        minutes = (ts.duration.seconds % 3600) // 60
        
        # Format duration string
        if hours > 0 and minutes > 0:
            duration_str = f"{hours} hour{'s' if hours != 1 else ''} and {minutes} minute{'s' if minutes != 1 else ''}"
        elif hours > 0:
            duration_str = f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            duration_str = f"{minutes} minute{'s' if minutes != 1 else ''}"
        
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
        hours = session_duration.seconds // 3600
        minutes = (session_duration.seconds % 3600) // 60
        
        # Format duration string
        if hours > 0 and minutes > 0:
            duration_str = f"{hours} hour{'s' if hours != 1 else ''} and {minutes} minute{'s' if minutes != 1 else ''}"
        elif hours > 0:
            duration_str = f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            duration_str = f"{minutes} minute{'s' if minutes != 1 else ''}"
        
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
    

