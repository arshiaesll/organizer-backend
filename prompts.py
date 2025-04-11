RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "newly_scheduled_assignments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "assignment_name": {"type": "string"},
                    "due_date": {"type": "string", "format": "date-time"},
                    "expected_completion_time": {"type": "number"},
                    "sessions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "start_time": {"type": "string", "format": "date-time"},
                                "duration": {
                                    "type": "number",
                                    "description": "Duration in seconds. Must be at least min_study_length and at most max_study_length."
                                },
                                "session_number": {"type": "integer"}
                            },
                            "required": ["start_time", "duration", "session_number"]
                        }
                    }
                },
                "required": ["assignment_name", "due_date", "sessions"]
            }
        }
    },
    "required": ["newly_scheduled_assignments"]
}