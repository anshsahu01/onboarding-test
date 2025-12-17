"""
Field definitions for onboarding.
Defines WHAT we collect, not HOW we ask.
"""

from typing import Optional
from enum import Enum


class FieldType(str, Enum):
    MANDATORY = "mandatory"
    


# === FIELD DEFINITIONS ===
# These tell the LLM what to collect and how to validate

FIELDS = {
    "name": {
        "type": FieldType.MANDATORY,
        "description": "User's full name",
        "validation_hint": "Must be a real name, not numbers or gibberish",
        "examples": ["Rahul", "Sarah Chen", "John Doe"],
        "first_question": "Hey, what do we call you?",  # ONLY hardcoded question
    },
    
    "role": {
        "type": FieldType.MANDATORY,
        "description": "Target job role(s) the user is looking for",
        "examples": ["Software Engineer", "Backend Developer", "Product Manager", "UX Designer", "Data Scientist"],
    },
    
    "experience_level": {
        "type": FieldType.MANDATORY,
        "description": "Years of experience or seniority level",
        "normalize_to": ["Entry-level", "Junior", "Mid-level", "Senior", "Lead"],
        "normalization_rules": {
            "0-1 years": "Entry-level",
            "1-2 years": "Junior", 
            "3-5 years": "Mid-level",
            "5-8 years": "Senior",
            "8+ years": "Lead",
        },
    },
    
    "location": {
        "type": FieldType.MANDATORY,
        "description": "Where the user wants to work (city, state, or remote)",
        "examples": ["San Francisco", "New York", "Remote", "Bangalore", "London"],
    },
    
    "startup_stage": {
        "type": FieldType.MANDATORY,
        "description": "Preferred stage of startup",
        "options": ["Early", "Growth", "Late", "Unicorn"],
        "option_descriptions": {
            "Early": "Pre-seed to Series A, small team, high risk/reward",
            "Growth": "Series B-C, scaling fast, established product",
            "Late": "Series D+, more stable, larger teams",
            "Unicorn": "1B+ valuation, well-established",
        },
    },
    
   "extra_preferences": {
    "type": FieldType.MANDATORY,
    "description": "Any additional preferences like industry, benefits, company culture, specific companies",
},
}

# Order in which fields should be collected
FIELD_ORDER = ["name", "role", "experience_level", "location", "startup_stage", "extra_preferences"]

# Completion messages (still hardcoded - these are our brand voice)
COMPLETION = {
    "message": "Cool, let us pull up the best startup roles for you. We'll start sending them to you!",
    "animation": "pspspspsps… pulling jobs…",
}

# Personality guidelines for the LLM
PERSONALITY = {
    "voice": "we/us (never I/me)",
    "tone": "friendly, casual, reliable",
    "style_words": ["cool", "nice", "got it", "sounds good", "awesome"],
    "message_length": "1-2 sentences max",
    "rules": [
        "Never be robotic or formal",
        "Acknowledge user's answer briefly before asking next question",
        "Combine related questions naturally when it makes sense",
        "If user provides multiple pieces of info, extract all of them",
        "Keep the energy positive and light",
    ],
}






#helper function 

def get_field_order()->list[str]:
    return FIELD_ORDER.copy()



def get_missing_fields(profile)->list[str]:
    missing = []

    for field_name in FIELD_ORDER:
        field_config = FIELDS[field_name]
        current_value = getattr(profile,field_name,None)
    if current_value is None or current_value=="":

            missing.append(field_name)
        
        

    return missing


def get_collected_field(profile)->dict:

    collected = {}

    for field_name in FIELD_ORDER:
        current_value = getattr(profile,field_name,None)

        if current_value is not None and current_value != "":
            collected[field_name] = current_value

    return collected


def get_first_question()->str:
    return FIELDS["name"]["first_question"]






def build_fields_description() -> str:
    """
    Build a description of all fields for the LLM prompt.
    """
    lines = []


    for field_name in FIELD_ORDER:
        field = FIELDS[field_name]
        
        field_type = "Required" if field["type"] == FieldType.MANDATORY else "Optional"
        
        line = f"- {field_name} ({field_type}): {field['description']}"
        
        if "examples" in field:
            line += f"\n  Examples: {', '.join(field['examples'])}"
        
        if "options" in field:
            line += f"\n  Options: {', '.join(field['options'])}"
        
        if "normalize_to" in field:
            line += f"\n  Normalize to: {', '.join(field['normalize_to'])}"
        
        lines.append(line)
    
    return "\n".join(lines)






