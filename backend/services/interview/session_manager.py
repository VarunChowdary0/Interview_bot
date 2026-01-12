from typing import Optional
from datetime import datetime
from functools import lru_cache
import threading

from models.interview import InterviewSession, InterviewState


class SessionManager:
    """In-memory session storage for interview sessions.

    Thread-safe implementation for managing interview sessions.
    For production, replace with Redis or database-backed storage.
    """

    def __init__(self):
        self._sessions: dict[str, InterviewSession] = {}
        self._resume_sessions: dict[str, dict] = {}  # Temporary resume storage
        self._lock = threading.Lock()

    def create_session(
        self,
        resume_data: Optional[dict] = None,
        job_data: Optional[dict] = None,
    ) -> InterviewSession:
        """Create a new interview session.

        Args:
            resume_data: Parsed resume data.
            job_data: Job description data.

        Returns:
            New InterviewSession instance.
        """
        session = InterviewSession(
            resume_data=resume_data,
            job_data=job_data,
        )

        with self._lock:
            self._sessions[session.session_id] = session

        return session

    def get_session(self, session_id: str) -> Optional[InterviewSession]:
        """Get a session by ID.

        Args:
            session_id: The session ID.

        Returns:
            InterviewSession if found, None otherwise.
        """
        with self._lock:
            return self._sessions.get(session_id)

    def update_session(self, session: InterviewSession) -> None:
        """Update an existing session.

        Args:
            session: The session to update.
        """
        with self._lock:
            if session.session_id in self._sessions:
                self._sessions[session.session_id] = session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session by ID.

        Args:
            session_id: The session ID.

        Returns:
            True if deleted, False if not found.
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def list_sessions(self, state: Optional[InterviewState] = None) -> list[InterviewSession]:
        """List all sessions, optionally filtered by state.

        Args:
            state: Optional state filter.

        Returns:
            List of matching sessions.
        """
        with self._lock:
            sessions = list(self._sessions.values())
            if state:
                sessions = [s for s in sessions if s.state == state]
            return sessions

    # Resume session management (temporary storage before interview creation)

    def store_resume(self, session_id: str, resume_data: dict) -> None:
        """Store parsed resume data temporarily.

        Args:
            session_id: The resume session ID.
            resume_data: Parsed resume data.
        """
        with self._lock:
            self._resume_sessions[session_id] = {
                "data": resume_data,
                "created_at": datetime.utcnow(),
            }

    def get_resume(self, session_id: str) -> Optional[dict]:
        """Get stored resume data.

        Args:
            session_id: The resume session ID.

        Returns:
            Resume data if found, None otherwise.
        """
        with self._lock:
            entry = self._resume_sessions.get(session_id)
            if entry:
                return entry["data"]
            return None

    def delete_resume(self, session_id: str) -> bool:
        """Delete stored resume data.

        Args:
            session_id: The resume session ID.

        Returns:
            True if deleted, False if not found.
        """
        with self._lock:
            if session_id in self._resume_sessions:
                del self._resume_sessions[session_id]
                return True
            return False

    def cleanup_expired(self, max_age_minutes: int = 60) -> int:
        """Clean up expired sessions.

        Args:
            max_age_minutes: Maximum age in minutes.

        Returns:
            Number of sessions cleaned up.
        """
        now = datetime.utcnow()
        cleaned = 0

        with self._lock:
            # Clean up interview sessions
            expired_sessions = [
                sid for sid, session in self._sessions.items()
                if (now - session.created_at).total_seconds() > max_age_minutes * 60
                and session.state in (InterviewState.COMPLETED, InterviewState.CANCELLED)
            ]
            for sid in expired_sessions:
                del self._sessions[sid]
                cleaned += 1

            # Clean up resume sessions
            expired_resumes = [
                sid for sid, entry in self._resume_sessions.items()
                if (now - entry["created_at"]).total_seconds() > max_age_minutes * 60
            ]
            for sid in expired_resumes:
                del self._resume_sessions[sid]
                cleaned += 1

        return cleaned


# Singleton instance
_session_manager: Optional[SessionManager] = None


@lru_cache()
def get_session_manager() -> SessionManager:
    """Get the singleton session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
