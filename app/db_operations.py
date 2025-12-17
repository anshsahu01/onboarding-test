# """
# Simple database operations for onboarding sessions.
# All CRUD operations for sessions and profiles.
# """
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select
# from sqlalchemy.orm import selectinload
# import uuid
# from datetime import datetime

# from app.models_db.db_models import OnboardingSession, UserProfile, SessionStatusEnum


# async def create_session(db: AsyncSession, user_id: str) -> OnboardingSession:
#     """Create a new onboarding session with empty profile."""
#     try:
#         session_id = uuid.uuid4()
#         print(f"  >> Generated session_id: {session_id}")

#         # Create session
#         session = OnboardingSession(
#             session_id=session_id,
#             user_id=user_id,
#             status=SessionStatusEnum.IN_PROGRESS,
#             created_at=datetime.utcnow(),
#             conversation_history=[]
#         )
#         print(f"  >> Created OnboardingSession object")

#         # Create empty profile
#         profile = UserProfile(
#             profile_id=uuid.uuid4(),
#             session_id=session_id,
#             user_id=user_id,
#             created_at=datetime.utcnow(),
#             updated_at=datetime.utcnow()
#         )
#         print(f"  >> Created UserProfile object")

#         db.add(session)
#         db.add(profile)
#         print(f"  >> Added objects to session")

#         await db.commit()
#         print(f"  >> Committed to database")

#         # Reload session with profile relationship
#         print(f"  >> Reloading session with profile...")
#         result = await db.execute(
#             select(OnboardingSession)
#             .options(selectinload(OnboardingSession.profile))
#             .where(OnboardingSession.session_id == session_id)
#         )
#         session = result.scalar_one()
#         print(f"  >> Session reloaded. Profile loaded: {session.profile is not None}")

#         print(f">> Created session: {session.session_id} for user: {user_id}")
#         return session

#     except Exception as e:
#         print(f"  >> ERROR in create_session: {type(e).__name__}: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         raise


# async def get_session(db: AsyncSession, session_id: uuid.UUID) -> OnboardingSession | None:
#     """Get a session by ID with its profile loaded."""

#     result = await db.execute(
#         select(OnboardingSession)
#         .options(selectinload(OnboardingSession.profile))
#         .where(OnboardingSession.session_id == session_id)
#     )

#     return result.scalar_one_or_none()


# async def add_message(db: AsyncSession, session_id: uuid.UUID, role: str, content: str):
#     """Add a message to conversation history."""
#     try:
#         print(f"  >> add_message called: session_id={session_id}, role={role}")

#         session = await get_session(db, session_id)
#         if not session:
#             print(f"  >> ERROR: Session not found: {session_id}")
#             return

#         # print(f"  >> Session found. Current history length: {len(session.conversation_history)}")

#         if session.conversation_history is None:
#             session.conversation_history = []

        
#         print(f"  >> Session found. Current history length: {len(session.conversation_history)}")


#         message = {
#             "role": role,
#             "content": content,
#             "timestamp": datetime.utcnow().isoformat()
#         }

#         session.conversation_history.append(message)
#         print(f"  >> Message appended. New history length: {len(session.conversation_history)}", flush=True)


        
#         # Mark as modified for JSONB column
#         from sqlalchemy.orm.attributes import flag_modified
#         flag_modified(session, "conversation_history")
#         print(f"  >> Marked conversation_history as modified")

#         await db.commit()
#         print(f"  >> Committed message to database")

#     except Exception as e:
#         print(f"  >> ERROR in add_message: {type(e).__name__}: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         raise


# async def update_profile(
#     db: AsyncSession,
#     session_id: uuid.UUID,
#     **profile_fields
# ):
#     """Update profile fields for a session."""

#     result = await db.execute(
#         select(UserProfile).where(UserProfile.session_id == session_id)
#     )
#     profile = result.scalar_one_or_none()

#     if not profile:
#         return

#     # Update only provided fields
#     for field, value in profile_fields.items():
#         if hasattr(profile, field) and value is not None:
#             setattr(profile, field, value)
#             print(f"  >> Set {field} = {value}")

#     profile.updated_at = datetime.utcnow()
#     await db.commit()


# async def mark_complete(db: AsyncSession, session_id: uuid.UUID):
#     """Mark a session as completed."""

#     session = await get_session(db, session_id)
#     if session:
#         session.status = SessionStatusEnum.COMPLETED
#         await db.commit()
#         print(f">> Session completed: {session_id}")


"""
Simple database operations for onboarding sessions.
All CRUD operations for sessions and profiles.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import uuid
from datetime import datetime
import logging

from app.models_db.db_models import OnboardingSession, UserProfile, SessionStatusEnum
from app.logging_config import get_logger

# Get logger
logger = get_logger("app.db_operations")

async def create_session(db: AsyncSession, user_id: str) -> OnboardingSession:
    """Create a new onboarding session with empty profile."""
    try:
        session_id = uuid.uuid4()
        logger.info(f"Generated session_id: {session_id}")

        # Create session
        session = OnboardingSession(
            session_id=session_id,
            user_id=user_id,
            status=SessionStatusEnum.IN_PROGRESS,
            created_at=datetime.utcnow(),
            conversation_history=[]
        )
        logger.info("Created OnboardingSession object")

        # Create empty profile
        profile = UserProfile(
            profile_id=uuid.uuid4(),
            session_id=session_id,
            user_id=user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        logger.info("Created UserProfile object")

        db.add(session)
        db.add(profile)
        logger.info("Added objects to session")

        await db.commit()
        logger.info("Committed to database")

        # Reload session with profile relationship
        logger.info("Reloading session with profile...")
        result = await db.execute(
            select(OnboardingSession)
            .options(selectinload(OnboardingSession.profile))
            .where(OnboardingSession.session_id == session_id)
        )
        session = result.scalar_one()
        logger.info(f"Session reloaded. Profile loaded: {session.profile is not None}")
        logger.info(f"Created session: {session.session_id} for user: {user_id}")
        
        return session

    except Exception as e:
        logger.error(f"ERROR in create_session: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise


async def get_session(db: AsyncSession, session_id: uuid.UUID) -> OnboardingSession | None:
    """Get a session by ID with its profile loaded."""
    result = await db.execute(
        select(OnboardingSession)
        .options(selectinload(OnboardingSession.profile))
        .where(OnboardingSession.session_id == session_id)
    )
    return result.scalar_one_or_none()


async def add_message(db: AsyncSession, session_id: uuid.UUID, role: str, content: str):
    """Add a message to conversation history."""
    try:
        logger.info(f"add_message called: session_id={session_id}, role={role}")

        session = await get_session(db, session_id)
        if not session:
            logger.error(f"ERROR: Session not found: {session_id}")
            return

        # Handle NoneType for conversation_history (Fixes the crash)
        if session.conversation_history is None:
            session.conversation_history = []
            logger.warning("conversation_history was None, initialized to []")

        logger.info(f"Session found. Current history length: {len(session.conversation_history)}")

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Append message (Only once!)
        session.conversation_history.append(message)
        logger.info(f"Message appended. New history length: {len(session.conversation_history)}")

        # Mark as modified for JSONB column
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(session, "conversation_history")
        logger.info("Marked conversation_history as modified")

        await db.commit()
        logger.info("Committed message to database")

    except Exception as e:
        logger.error(f"ERROR in add_message: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise


async def update_profile(
    db: AsyncSession,
    session_id: uuid.UUID,
    **profile_fields
):
    """Update profile fields for a session."""
    try:
        result = await db.execute(
            select(UserProfile).where(UserProfile.session_id == session_id)
        )
        profile = result.scalar_one_or_none()

        if not profile:
            logger.warning(f"UserProfile not found for session: {session_id}")
            return

        # Update only provided fields
        for field, value in profile_fields.items():
            if hasattr(profile, field) and value is not None:
                setattr(profile, field, value)
                logger.info(f"Set {field} = {value}")

        profile.updated_at = datetime.utcnow()
        await db.commit()
        logger.info(f"Profile updated for session: {session_id}")
        
    except Exception as e:
        logger.error(f"ERROR in update_profile: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise


async def mark_complete(db: AsyncSession, session_id: uuid.UUID):
    """Mark a session as completed."""
    try:
        session = await get_session(db, session_id)
        if session:
            session.status = SessionStatusEnum.COMPLETED
            await db.commit()
            logger.info(f"Session completed: {session_id}")
        else:
            logger.warning(f"Could not mark complete - session not found: {session_id}")
            
    except Exception as e:
        logger.error(f"ERROR in mark_complete: {type(e).__name__}: {str(e)}")
        raise
