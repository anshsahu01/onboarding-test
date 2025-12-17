"""
Pydantic models for the onboarding API.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# === API REQUEST MODELS ===

class InitRequest(BaseModel):
    """Request to start a new onboarding session."""
    user_id: str


class AnswerRequest(BaseModel):
    """Request to submit an answer."""
    session_id: str
    answer: str


# === CORE DATA MODELS ===

class UserProfile(BaseModel):
    """
    User profile data collected during onboarding.
    Fields match FIELD_ORDER in questions.py
    """
    name: Optional[str] = None
    role: Optional[str] = None
    experience_level: Optional[str] = None
    location: Optional[str] = None
    startup_stage: Optional[str] = None
    extra_preferences: Optional[str] = None


class SessionStatus(str, Enum):
    """Session status options."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class SessionData(BaseModel):
    """
    Full session state.
    Tracks everything about an onboarding conversation.
    """
    session_id: str
    user_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: SessionStatus = SessionStatus.IN_PROGRESS
    
    # Collected profile data
    profile: UserProfile = Field(default_factory=UserProfile)
    
    # Conversation history
    # Format: [{"question": "...", "answer": "...", "timestamp": "..."}, ...]
    conversation_history: List[Dict[str, Any]] = []


# === API RESPONSE MODELS ===

class OnboardingResponse(BaseModel):
    """
    Response from onboarding endpoints.
    Used for both /start and /answer endpoints.
    """
    session_id: str
    success: bool = True
    response: str  # The bot's message to display
    is_complete: bool = False
    profile: Optional[UserProfile] = None
    
    # Only included on completion
    completion_message: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response structure."""
    success: bool = False
    error: str
    detail: Optional[str] = None