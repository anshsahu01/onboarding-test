"""
In-memory session manager for onboarding sessions.
This is a temporary implementation before database integration.
"""

from typing import Dict, Optional
from datetime import datetime
import uuid

from app.models import SessionData, SessionStatus, UserProfile


class SessionManager:
    """
    In-memory session storage.
    Stores active onboarding sessions in a dictionary.
    """

    def __init__(self):
        self._sessions: Dict[str, SessionData] = {}

    def create_session(self, user_id: str) -> SessionData:
        """
        Create a new onboarding session.

        Args:
            user_id: The user's ID

        Returns:
            SessionData: New session object
        """
        session_id = str(uuid.uuid4())

        session = SessionData(
            session_id=session_id,
            user_id=user_id,
            created_at=datetime.utcnow(),
            status=SessionStatus.IN_PROGRESS,
            profile=UserProfile(),
            conversation_history=[]
        )

        self._sessions[session_id] = session
        print(f"✅ Created new session: {session_id} for user: {user_id}")

        return session

    def get_session(self, session_id: str) -> Optional[SessionData]:
        """
        Retrieve a session by ID.

        Args:
            session_id: The session ID

        Returns:
            SessionData or None if not found
        """
        return self._sessions.get(session_id)

    def update_session(self, session: SessionData) -> None:
        """
        Update an existing session.

        Args:
            session: The session object to update
        """
        self._sessions[session.session_id] = session

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str
    ) -> None:
        """
        Add a message to the conversation history.

        Args:
            session_id: The session ID
            role: Message role ("user" or "assistant")
            content: Message content
        """
        session = self.get_session(session_id)
        if session:
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat()
            }
            session.conversation_history.append(message)
            self.update_session(session)

    def mark_complete(self, session_id: str) -> None:
        """
        Mark a session as completed.

        Args:
            session_id: The session ID
        """
        session = self.get_session(session_id)
        if session:
            session.status = SessionStatus.COMPLETED
            self.update_session(session)
            print(f"✅ Session completed: {session_id}")

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: The session ID

        Returns:
            bool: True if deleted, False if not found
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            print(f"🗑️  Deleted session: {session_id}")
            return True
        return False

    def get_all_sessions(self) -> Dict[str, SessionData]:
        """
        Get all sessions (for debugging).

        Returns:
            Dict of all sessions
        """
        return self._sessions

    def clear_all(self) -> None:
        """
        Clear all sessions (for testing/cleanup).
        """
        count = len(self._sessions)
        self._sessions.clear()
        print(f"🗑️  Cleared {count} sessions")


# Global instance
session_manager = SessionManager()
