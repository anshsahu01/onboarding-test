"""
FastAPI application for AI-powered onboarding.
"""
import sys
import asyncio
import logging
import traceback

# FORCE WINDOWS TO USE THE CORRECT EVENT LOOP
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv import load_dotenv
import os 

# Load .env first
loaded = load_dotenv()

# Then configure centralized logging
from app.logging_config import configure_logging, get_logger
configure_logging()
logger = get_logger("main")

logger.info("=== ENV DEBUG ===")
logger.info(f".env loaded: {loaded}")
logger.info(f"DEEPSEEK_API_URL: {os.getenv('DEEPSEEK_API_URL')}")
logger.info(f"DEEPSEEK_API_KEY: {'SET' if os.getenv('DEEPSEEK_API_KEY') else 'NOT SET'}")
logger.info("=================")

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db, engine

from app.models import (
    InitRequest,
    AnswerRequest,
    OnboardingResponse,
    SessionStatus,
    UserProfile as PydanticUserProfile,
)
from app.services import process_message
from app.questions import get_first_question, COMPLETION
import app.db_operations as db_ops
from app.models_db.db_models import SessionStatusEnum

# === LIFESPAN & APP SETUP ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info(">> Onboarding API starting...")
    
    # Check Database Connection on Startup
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            logger.info("[OK] CONNECTION SUCCESSFUL!")
            logger.info(f"     DB Version: {result.scalar()}")
    except Exception as e:
        logger.error(f"[ERROR] CONNECTION FAILED: {e}")
        # We don't raise here to allow the app to start even if DB is flaky, 
        # but requests will fail.
    
    yield
    
    logger.info(">> Onboarding API shutting down...")
    await engine.dispose()

app = FastAPI(
    title="Onboarding API",
    description="AI-powered job seeker onboarding",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - allow frontend to call API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === MIDDLEWARE ===

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every incoming request and its result."""
    logger.info(f"👉 MIDDLEWARE: Received {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        logger.info(f"✅ MIDDLEWARE: Response code {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"❌ MIDDLEWARE: Request failed with {e}")
        raise

# === EXCEPTION HANDLERS ===

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle 422 Validation Errors gracefully."""
    logger.warning(f"⚠️ VALIDATION ERROR at {request.url}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "message": "Invalid data sent"}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for 500 errors."""
    logger.error(f"🔥 GLOBAL CRASH on {request.method} {request.url.path}")
    logger.error(f"Error Type: {type(exc).__name__}")
    logger.error(f"Error Message: {str(exc)}")
    logger.error(traceback.format_exc()) # Print full stack trace

    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

# === ENDPOINTS ===

@app.get("/test-db")
async def test_endpoint(db: AsyncSession = Depends(get_db)):
    # Endpoint to test manually
    try:
        result = await db.execute(text("SELECT 1"))
        return {"status": "success", "result": result.scalar()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Onboarding API",
        "version": "1.0.0"
    }


@app.post("/api/onboarding/start", response_model=OnboardingResponse)
async def start_onboarding(request: InitRequest, db: AsyncSession = Depends(get_db)):
    """
    Start a new onboarding session.
    Returns the first question (hardcoded).
    """
    try:
        logger.info(f"{'='*60}")
        logger.info(f">> START ONBOARDING REQUEST for User ID: {request.user_id}")

        # Create new session in database
        logger.info(">> Creating session in database...")
        session = await db_ops.create_session(db, request.user_id)
        logger.info(f">> Session created: {session.session_id}")

        # Get the first question
        first_question = get_first_question()
        logger.info(f">> First question: {first_question}")

        # Add first question to history
        logger.info(">> Adding first question to history...")
        await db_ops.add_message(
            db=db,
            session_id=session.session_id,
            role="assistant",
            content=first_question
        )
        logger.info(">> Message added successfully")

        response = OnboardingResponse(
            session_id=str(session.session_id),
            success=True,
            response=first_question,
            is_complete=False,
        )
        logger.info(f">> Returning response for session {session.session_id}")
        return response

    except Exception as e:
        logger.error(">> ERROR IN START ONBOARDING")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/api/onboarding/answer", response_model=OnboardingResponse)
async def submit_answer(request: AnswerRequest, db: AsyncSession = Depends(get_db)):
    """
    Submit an answer and get the next question.
    """
    import uuid as uuid_module

    logger.info(f"{'='*60}")
    logger.info(f">> ANSWER REQUEST Session ID: {request.session_id}")
    logger.info(f"User Answer: {request.answer}")

    # Get session from database
    session_uuid = uuid_module.UUID(request.session_id)
    session = await db_ops.get_session(db, session_uuid)

    if session is None:
        logger.warning(f">> Session not found: {request.session_id}")
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status == SessionStatusEnum.COMPLETED:
        logger.warning(">> Session already completed")
        raise HTTPException(status_code=400, detail="Session already completed")

    logger.info(f">> Processing message. Current history length: {len(session.conversation_history)}")

    # Convert DB session to format that process_message expects
    from app.models import SessionData
    temp_session = SessionData(
        session_id=str(session.session_id),
        user_id=session.user_id,
        status=SessionStatus.IN_PROGRESS,
        profile=PydanticUserProfile(
            name=session.profile.name,
            role=session.profile.role,
            experience_level=session.profile.experience_level,
            location=session.profile.location,
            startup_stage=session.profile.startup_stage,
            extra_preferences=session.profile.extra_preferences
        ),
        conversation_history=session.conversation_history
    )

    # Process with LLM
    result = await process_message(temp_session, request.answer)

    logger.info(">> LLM RESULT:")
    logger.info(f"Response: {result['response']}")
    logger.info(f"Extracted: {result['extracted']}")
    logger.info(f"Is complete: {result.get('is_complete', False)}")

    # Add user message to database
    await db_ops.add_message(
        db=db,
        session_id=session_uuid,
        role="user",
        content=request.answer
    )

    # Add LLM response to database
    await db_ops.add_message(
        db=db,
        session_id=session_uuid,
        role="assistant",
        content=result["response"]
    )

    # Update profile with extracted data
    if result.get('extracted'):
        await db_ops.update_profile(db, session_uuid, **result['extracted'])

    # Handle completion
    if result.get("is_complete"):
        await db_ops.mark_complete(db, session_uuid)

        # Reload session to get updated profile
        session = await db_ops.get_session(db, session_uuid)

        return OnboardingResponse(
            session_id=str(session.session_id),
            success=True,
            response=result["response"],
            is_complete=True,
            profile=PydanticUserProfile(
                name=session.profile.name,
                role=session.profile.role,
                experience_level=session.profile.experience_level,
                location=session.profile.location,
                startup_stage=session.profile.startup_stage,
                extra_preferences=session.profile.extra_preferences
            ),
            completion_message=COMPLETION["animation"],
        )

    return OnboardingResponse(
        session_id=str(session.session_id),
        success=True,
        response=result["response"],
        is_complete=False,
    )


@app.get("/api/onboarding/session/{session_id}")
async def get_session_endpoint(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get current session state.
    """
    import uuid as uuid_module
    
    try:
        session_uuid = uuid_module.UUID(session_id)
        session = await db_ops.get_session(db, session_uuid)

        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "session_id": str(session.session_id),
            "user_id": session.user_id,
            "status": session.status.value,
            "profile": {
                "name": session.profile.name,
                "role": session.profile.role,
                "experience_level": session.profile.experience_level,
                "location": session.profile.location,
                "startup_stage": session.profile.startup_stage,
                "extra_preferences": session.profile.extra_preferences,
            },
            "conversation_history": session.conversation_history,
            "created_at": session.created_at.isoformat(),
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")






# """
# FastAPI application for AI-powered onboarding.


# """
# import sys
# import asyncio

# # FORCE WINDOWS TO USE THE CORRECT EVENT LOOP
# if sys.platform == "win32":
#     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# from fastapi import FastAPI
# # ... rest of your imports and code






# from dotenv import load_dotenv
# import os 
# # Load .env and debug
# loaded = load_dotenv()
# print(f"=== ENV DEBUG ===")
# print(f".env loaded: {loaded}")
# print(f"DEEPSEEK_API_URL: {os.getenv('DEEPSEEK_API_URL')}")
# print(f"DEEPSEEK_API_KEY: {'SET' if os.getenv('DEEPSEEK_API_KEY') else 'NOT SET'}")
# print(f"=================") 

# from fastapi import FastAPI, HTTPException, Depends
# from fastapi.middleware.cors import CORSMiddleware
# from contextlib import asynccontextmanager

# from sqlalchemy import text
# from sqlalchemy.ext.asyncio import AsyncSession
# from app.db import get_db, engine

# from app.models import (
#     InitRequest,
#     AnswerRequest,
#     OnboardingResponse,
#     SessionStatus,
#     UserProfile as PydanticUserProfile,
# )
# from app.services import process_message
# from app.questions import get_first_question, COMPLETION
# import app.db_operations as db_ops
# from app.models_db.db_models import SessionStatusEnum





# # === APP SETUP ===

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """Startup and shutdown events."""
#     print(">> Onboarding API starting...")
#     yield
#     print(">> Onboarding API shutting down...")


# app = FastAPI(
#     title="Onboarding API",
#     description="AI-powered job seeker onboarding",
#     version="1.0.0",
#     lifespan=lifespan,
# )


# # Add this AFTER "app = FastAPI(...)" and BEFORE "app.add_middleware(...)"

# @app.middleware("http")
# async def log_requests(request: Request, call_next):
#     print(f"👉 MIDDLEWARE: Received {request.method} {request.url}", flush=True)
#     try:
#         response = await call_next(request)
#         print(f"✅ MIDDLEWARE: Response code {response.status_code}", flush=True)
#         return response
#     except Exception as e:
#         print(f"❌ MIDDLEWARE: Request failed with {e}", flush=True)
#         raise

# # CORS - allow frontend to call API
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # In production, specify your frontend URL
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# from fastapi.exceptions import RequestValidationError

# # Add this BEFORE your global @app.exception_handler(Exception)

# @app.exception_handler(RequestValidationError)
# async def validation_exception_handler(request: Request, exc: RequestValidationError):
#     print(f"⚠️ VALIDATION ERROR: {exc.errors()}", flush=True)
#     return JSONResponse(
#         status_code=422,
#         content={"detail": exc.errors(), "message": "Invalid data sent"}
#     )

# # Global exception handler to catch all errors
# from fastapi import Request
# from fastapi.responses import JSONResponse

# @app.exception_handler(Exception)
# async def global_exception_handler(request: Request, exc: Exception):
#     print(f"\n{'='*60}")
#     print(f">> GLOBAL EXCEPTION HANDLER")
#     print(f"Path: {request.url.path}")
#     print(f"Method: {request.method}")
#     print(f"Exception Type: {type(exc).__name__}")
#     print(f"Exception Message: {str(exc)}")
#     print(f"{'='*60}")
#     import traceback
#     traceback.print_exc()

#     return JSONResponse(
#         status_code=500,
#         content={"detail": f"Internal server error: {str(exc)}"}
#     )


# # === ENDPOINTS ===

# @app.on_event("startup")
# async def check_connection():
#     # This runs when you start the server to verify DB connection
#     try:
#         async with engine.connect() as conn:
#             result = await conn.execute(text("SELECT version()"))
#             print("[OK] CONNECTION SUCCESSFUL!")
#             print(f"   DB Version: {result.scalar()}")
#     except Exception as e:
#         print("[ERROR] CONNECTION FAILED")
#         print(f"   Error: {e}")

# @app.get("/test-db")
# async def test_endpoint(db: AsyncSession = Depends(get_db)):
#     # Endpoint to test manually
#     try:
#         result = await db.execute(text("SELECT 1"))
#         return {"status": "success", "result": result.scalar()}
#     except Exception as e:
#         return {"status": "error", "message": str(e)}

# @app.get("/")
# async def root():
#     """Health check endpoint."""
#     return {
#         "status": "ok",
#         "service": "Onboarding API",
#         "version": "1.0.0"
#     }


# @app.post("/api/onboarding/start", response_model=OnboardingResponse)
# async def start_onboarding(request: InitRequest, db: AsyncSession = Depends(get_db)):
#     """
#     Start a new onboarding session.
#     Returns the first question (hardcoded).
#     """
#     try:
#         print(f"\n{'='*60}")
#         print(f">> START ONBOARDING REQUEST")
#         print(f"User ID: {request.user_id}")
#         print(f"{'='*60}")

#         # Create new session in database
#         print(">> Creating session in database...")
#         session = await db_ops.create_session(db, request.user_id)
#         print(f">> Session created: {session.session_id}")
#         print(f">> Session has profile: {session.profile is not None}")

#         # Get the first question
#         print(">> Getting first question...")
#         first_question = get_first_question()
#         print(f">> First question: {first_question}")

#         # Add first question to history
#         print(">> Adding first question to history...")
#         await db_ops.add_message(
#             db=db,
#             session_id=session.session_id,
#             role="assistant",
#             content=first_question
#         )
#         print(">> Message added successfully")

#         response = OnboardingResponse(
#             session_id=str(session.session_id),
#             success=True,
#             response=first_question,
#             is_complete=False,
#         )
#         print(f">> Returning response: {response}")
#         return response

#     except Exception as e:
#         print(f"\n{'='*60}")
#         print(f">> ERROR IN START ONBOARDING")
#         print(f"Error type: {type(e).__name__}")
#         print(f"Error message: {str(e)}")
#         print(f"{'='*60}")
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# @app.post("/api/onboarding/answer", response_model=OnboardingResponse)
# async def submit_answer(request: AnswerRequest, db: AsyncSession = Depends(get_db)):
#     """
#     Submit an answer and get the next question.
#     """
#     import uuid as uuid_module

#     print(f"\n{'='*60}")
#     print(f">> ANSWER REQUEST")
#     print(f"Session ID: {request.session_id}")
#     print(f"User Answer: {request.answer}")
#     print(f"{'='*60}")

#     # Get session from database
#     session_uuid = uuid_module.UUID(request.session_id)
#     session = await db_ops.get_session(db, session_uuid)

#     if session is None:
#         print(f">> Session not found: {request.session_id}")
#         raise HTTPException(status_code=404, detail="Session not found")

#     if session.status == SessionStatusEnum.COMPLETED:
#         raise HTTPException(status_code=400, detail="Session already completed")

#     print(f"\n>> BEFORE PROCESSING:")
#     print(f"Profile: {session.profile}")
#     print(f"History length: {len(session.conversation_history)}")

#     # Convert DB session to format that process_message expects
#     # Create a temporary object that looks like the old SessionData
#     from app.models import SessionData
#     temp_session = SessionData(
#         session_id=str(session.session_id),
#         user_id=session.user_id,
#         status=SessionStatus.IN_PROGRESS,
#         profile=PydanticUserProfile(
#             name=session.profile.name,
#             role=session.profile.role,
#             experience_level=session.profile.experience_level,
#             location=session.profile.location,
#             startup_stage=session.profile.startup_stage,
#             extra_preferences=session.profile.extra_preferences
#         ),
#         conversation_history=session.conversation_history
#     )

#     # Process with LLM
#     result = await process_message(temp_session, request.answer)

#     print(f"\n>> LLM RESULT:")
#     print(f"Response: {result['response']}")
#     print(f"Extracted: {result['extracted']}")
#     print(f"Is complete: {result.get('is_complete', False)}")

#     # Add user message to database
#     await db_ops.add_message(
#         db=db,
#         session_id=session_uuid,
#         role="user",
#         content=request.answer
#     )

#     # Add LLM response to database
#     await db_ops.add_message(
#         db=db,
#         session_id=session_uuid,
#         role="assistant",
#         content=result["response"]
#     )

#     # Update profile with extracted data
#     if result.get('extracted'):
#         await db_ops.update_profile(db, session_uuid, **result['extracted'])

#     # Handle completion
#     if result.get("is_complete"):
#         await db_ops.mark_complete(db, session_uuid)

#         # Reload session to get updated profile
#         session = await db_ops.get_session(db, session_uuid)

#         return OnboardingResponse(
#             session_id=str(session.session_id),
#             success=True,
#             response=result["response"],
#             is_complete=True,
#             profile=PydanticUserProfile(
#                 name=session.profile.name,
#                 role=session.profile.role,
#                 experience_level=session.profile.experience_level,
#                 location=session.profile.location,
#                 startup_stage=session.profile.startup_stage,
#                 extra_preferences=session.profile.extra_preferences
#             ),
#             completion_message=COMPLETION["animation"],
#         )

#     return OnboardingResponse(
#         session_id=str(session.session_id),
#         success=True,
#         response=result["response"],
#         is_complete=False,
#     )


# @app.get("/api/onboarding/session/{session_id}")
# async def get_session_endpoint(session_id: str, db: AsyncSession = Depends(get_db)):
#     """
#     Get current session state.
#     Useful for debugging or resuming sessions.
#     """
#     import uuid as uuid_module

#     session_uuid = uuid_module.UUID(session_id)
#     session = await db_ops.get_session(db, session_uuid)

#     if session is None:
#         raise HTTPException(status_code=404, detail="Session not found")

#     return {
#         "session_id": str(session.session_id),
#         "user_id": session.user_id,
#         "status": session.status.value,
#         "profile": {
#             "name": session.profile.name,
#             "role": session.profile.role,
#             "experience_level": session.profile.experience_level,
#             "location": session.profile.location,
#             "startup_stage": session.profile.startup_stage,
#             "extra_preferences": session.profile.extra_preferences,
#         },
#         "conversation_history": session.conversation_history,
#         "created_at": session.created_at.isoformat(),
#     }