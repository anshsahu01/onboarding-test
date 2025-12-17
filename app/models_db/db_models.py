from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum


from app.db import Base  # This imports from app/db.py (the file with engine setup)

# Enum for session status

class SessionStatusEnum(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"



class OnboardingSession(Base):
    """
    Docstring for OnboardingSession

    Tracks each onboarding conversation
    """
    __tablename__ = "onboarding_sessions"


    #Primary Key

    session_id = Column(UUID(as_uuid=True),primary_key=True, default=uuid.uuid4)

    #User identifier ()

    user_id = Column(String(255), nullable=False, index = True)

    #session metadata

    status = Column(SQLEnum(SessionStatusEnum), default=SessionStatusEnum.IN_PROGRESS, nullable=False)
    created_at = Column(DateTime,default=datetime.utcnow,nullable=False)


    # Conversation history stored as JSONB
    # Format: [{"role": "user/assistant", "content": "...", "timestamp": "..."}]
    conversation_history = Column(JSONB, default=list, nullable=False)
    
    # Relationship to profile (1:1)
    profile = relationship("UserProfile", back_populates="session", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<OnboardingSession(session_id={self.session_id}, user_id={self.user_id}, status={self.status})>"
    



class UserProfile(Base):
    """
    Stores collected onboarding data for a user.
    """
    __tablename__ = "user_profiles"

    # Primary Key
    profile_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign Key to session (1:1 relationship)
    session_id = Column(UUID(as_uuid=True), ForeignKey("onboarding_sessions.session_id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # User identifier (same as in session)
    user_id = Column(String(255), nullable=False, index=True)
    
    # Collected profile fields (all nullable, filled gradually)
    name = Column(String(255), nullable=True)
    role = Column(String(255), nullable=True)
    experience_level = Column(String(100), nullable=True)
    location = Column(String(255), nullable=True)
    startup_stage = Column(String(100), nullable=True)
    extra_preferences = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship back to session
    session = relationship("OnboardingSession", back_populates="profile")

    def __repr__(self):
        return f"<UserProfile(profile_id={self.profile_id}, user_id={self.user_id}, name={self.name})>"





