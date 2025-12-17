# for open AI key 

"""
LLM Service for onboarding.
Supports: OpenAI (GPT-4o), DeepSeek
"""

import json
import os
import httpx
import logging
import asyncio
from typing import Optional

from app.models import SessionData, UserProfile
from app.questions import (
    FIELDS,
    FIELD_ORDER,
    PERSONALITY,
    COMPLETION,
    build_fields_description,
    get_first_question,
)
from app.logging_config import get_logger

# === LOGGING SETUP ===
logger = get_logger("app.services")


# === CONFIGURATION ===
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")

# OpenAI config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o"

# DeepSeek config (backup)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_MODEL = "deepseek-chat"


# Gemini config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1

logger.info(f"LLM Provider: {LLM_PROVIDER}")
logger.info(f"OpenAI API Key: {'SET' if OPENAI_API_KEY else 'NOT SET'}")
logger.info(f"Gemini API Key: {'SET' if GEMINI_API_KEY else 'NOT SET'}")
logger.info(f"DeepSeek API Key: {'SET' if DEEPSEEK_API_KEY else 'NOT SET'}")


# === SYSTEM PROMPT ===

def _build_system_prompt() -> str:
    """Build the system prompt."""
    
    fields_desc = build_fields_description()
    personality_rules = "\n".join([f"- {rule}" for rule in PERSONALITY["rules"]])
    
    return f"""You are an onboarding assistant for a job platform helping job seekers find startup roles.

## YOUR PERSONALITY
- Always speak as "{PERSONALITY['voice']}" (never "I" or "me")  
- Tone: {PERSONALITY['tone']}
- Use words like: {', '.join(PERSONALITY['style_words'])}
- Keep messages to {PERSONALITY['message_length']}
- Rules:
{personality_rules}

## FIELDS TO COLLECT (in order)
{fields_desc}

## HOW TO TRACK PROGRESS
- Look at the conversation history to see what's already been extracted
- Your previous responses contain "extracted" data - those fields are DONE
- Only ask for fields that haven't been extracted yet
- NEVER ask for information already collected in previous turns

## YOUR TASK EACH TURN
1. Extract any relevant data from the user's LATEST message
2. Acknowledge their answer briefly (be warm, not robotic)
3. Ask for the next missing field naturally
4. If user provided multiple pieces of info, extract ALL of them
5. When ALL fields are collected, set "is_complete": true

## RESPONSE FORMAT
You MUST respond with valid JSON only (no markdown, no code blocks):
{{
    "extracted": {{
        "field_name": "value"
    }},
    "response": "Your acknowledgment + next question combined naturally",
    "is_complete": false
}}

IMPORTANT:
- "extracted" should ONLY contain NEW data from the CURRENT message
- "is_complete" is true ONLY when all 6 fields are collected
- If nothing new to extract, use empty object: "extracted": {{}}
- Return ONLY the JSON object, nothing else

## FIELD VALIDATION
- name: Must be a real name, not gibberish or numbers
- experience_level: Normalize to one of: Entry-level, Junior, Mid-level, Senior, Lead
  (0-1 yrs = Entry-level, 1-2 = Junior, 3-5 = Mid-level, 5-8 = Senior, 8+ = Lead)
- startup_stage: Must be one of: Early, Growth, Late, Unicorn

## WHEN COMPLETE
When all 6 fields are collected, respond with:
{{
    "extracted": {{}},
    "response": "{COMPLETION['message']}",
    "is_complete": true
}}
"""


_SYSTEM_PROMPT: Optional[str] = None

def get_system_prompt() -> str:
    """Get cached system prompt."""
    global _SYSTEM_PROMPT
    if _SYSTEM_PROMPT is None:
        _SYSTEM_PROMPT = _build_system_prompt()
    return _SYSTEM_PROMPT


# === VALIDATION ===

def _validate_llm_response(content: str) -> dict:
    """Validate and parse LLM response."""
    
    if not content or not content.strip():
        raise ValueError("LLM returned empty response")
    
    content = content.strip()
    
    # Handle markdown code blocks
    if content.startswith("```"):
        lines = content.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)
    
    # Parse JSONc
    parsed = json.loads(content)
    
    # Validate required fields
    if "response" not in parsed:
        raise ValueError("LLM response missing 'response' field")
    
    if not parsed.get("response", "").strip():
        raise ValueError("LLM returned empty 'response' field")
    
    # Set defaults
    if "extracted" not in parsed:
        parsed["extracted"] = {}
    
    if "is_complete" not in parsed:
        parsed["is_complete"] = False
    
    return parsed


# === LLM API CALLS ===

async def _call_openai(messages: list[dict], temperature: float = 0.7) -> dict:
    """Call OpenAI API (GPT-4o)."""
    
    system_prompt = get_system_prompt()
    
    api_messages = [{"role": "system", "content": system_prompt}]
    api_messages.extend(messages)
    
    request_body = {
        "model": OPENAI_MODEL,
        "messages": api_messages,
        "temperature": temperature,
        "max_tokens": 500,
        "response_format": {"type": "json_object"}
    }
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    logger.debug(f"=== OPENAI REQUEST ===")
    logger.debug(f"Model: {OPENAI_MODEL}")
    logger.debug(f"Messages count: {len(api_messages)}")
    logger.debug(f"Temperature: {temperature}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            OPENAI_API_URL,
            headers=headers,
            json=request_body
        )
        
        logger.debug(f"OpenAI Status: {response.status_code}")
        
        response.raise_for_status()
        
        api_response = response.json()

        if not api_response.get("choices"):
            raise ValueError("OpenAI returned no choices")
        
        content = api_response["choices"][0]["message"]["content"]
        logger.debug(f"OpenAI content: {content[:200]}")
        
        return _validate_llm_response(content)


async def _call_deepseek(messages: list[dict], temperature: float = 0.7) -> dict:
    """Call DeepSeek API."""
    
    system_prompt = get_system_prompt()
    
    api_messages = [{"role": "system", "content": system_prompt}]
    api_messages.extend(messages)
    
    request_body = {
        "model": DEEPSEEK_MODEL,
        "messages": api_messages,
        "temperature": temperature,
        "max_tokens": 500,
        "response_format": {"type": "json_object"}
    }
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    logger.debug(f"=== DEEPSEEK REQUEST ===")
    logger.debug(f"Messages count: {len(api_messages)}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=request_body
        )
        
        logger.debug(f"DeepSeek Status: {response.status_code}")
        
        response.raise_for_status()
        
        api_response = response.json()

        if not api_response.get("choices"):
            raise ValueError("DeepSeek returned no choices")
        
        content = api_response["choices"][0]["message"]["content"]
        
        return _validate_llm_response(content)



async def _call_gemini(conversation_history: list[dict], temperature: float = 0.7) -> dict:
    """
    Call Gemini API.

    Gemini uses a different format than OpenAI.
    """

    system_prompt = get_system_prompt()

    # Convert our format to Gemini format
    # Gemini wants: {"role": "user", "parts": [{"text": "..."}]}
    gemini_contents = []

    # Add system prompt as first user message (Gemini doesn't have system role in same way)
    # We'll prepend it to conversation context

    for msg in conversation_history:
        role = msg["role"]
        # Gemini uses "user" and "model" (not "assistant")
        if role == "assistant":
            role = "model"

        gemini_contents.append({
            "role": role,
            "parts": [{"text": msg["content"]}]
        })

    request_body = {
        "contents": gemini_contents,
        "systemInstruction": {
            "parts": [{"text": system_prompt}]
        },
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 500,
            "responseMimeType": "application/json"
        }
    }

    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"

    headers = {
        "Content-Type": "application/json"
    }

    logger.debug(f"=== GEMINI REQUEST ===")
    logger.debug(f"URL: {GEMINI_API_URL}")
    logger.debug(f"Messages count: {len(gemini_contents)}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            headers=headers,
            json=request_body
        )

        logger.debug(f"Gemini Status: {response.status_code}")
        logger.debug(f"Gemini Response: {response.text[:500]}")

        response.raise_for_status()

        api_response = response.json()

        # Gemini response structure:
        # {"candidates": [{"content": {"parts": [{"text": "..."}]}}]}

        if not api_response.get("candidates"):
            raise ValueError("Gemini returned no candidates")

        content = api_response["candidates"][0]["content"]["parts"][0]["text"]
        logger.debug(f"Gemini content: {content}")

        return _validate_llm_response(content)

# === UNIFIED LLM CALL WITH RETRY ===

async def call_llm(conversation_history: list[dict]) -> dict:
    """Call LLM with retry logic."""
    
    logger.info(f"Calling LLM provider: {LLM_PROVIDER}")
    
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            # Vary temperature on retry
            temperature = 0.7 + (attempt * 0.1)
            
            logger.info(f"Attempt {attempt + 1}/{MAX_RETRIES} (temp={temperature})")
            
            # Call appropriate provider
            if LLM_PROVIDER == "openai":
                result = await _call_openai(conversation_history, temperature)
            elif LLM_PROVIDER == "gemini":
                result = await _call_gemini(conversation_history, temperature)
            else:
                result = await _call_deepseek(conversation_history, temperature)
            
            logger.info(f"Success on attempt {attempt + 1}")
            logger.info(f"Extracted: {result.get('extracted', {})}")
            
            return result
            
        except httpx.HTTPStatusError as e:
            last_error = e
            logger.warning(f"HTTP error: {e.response.status_code} - {e.response.text[:200]}")
            
            if e.response.status_code in [401, 403]:
                logger.error("Authentication error - not retrying")
                break
                
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            logger.warning(f"Parse error: {e}")
            
        except Exception as e:
            last_error = e
            logger.warning(f"Unexpected error: {type(e).__name__}: {e}")
        
        if attempt < MAX_RETRIES - 1:
            delay = RETRY_DELAY_SECONDS * (2 ** attempt)
            logger.info(f"Waiting {delay}s before retry...")
            await asyncio.sleep(delay)
    
    logger.error(f"All {MAX_RETRIES} attempts failed. Last error: {last_error}")
    return _fallback_response("We're having trouble connecting. Could you try that again?")


def _fallback_response(message: str) -> dict:
    """Return safe fallback response."""
    return {
        "extracted": {},
        "response": message,
        "is_complete": False,
        "error": True
    }


# === MAIN PROCESSING ===

async def process_message(session: SessionData, user_message: str) -> dict:
    """Process a user message and return the next response."""

    conversation_history = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in session.conversation_history
    ]

    conversation_history.append({
        "role": "user",
        "content": user_message
    })

    print(f"\n🔍 CONVERSATION HISTORY SENT TO LLM:")
    for i, msg in enumerate(conversation_history):
        print(f"  {i+1}. [{msg['role']}]: {msg['content'][:100]}")

    llm_response = await call_llm(conversation_history)

    print(f"\n✨ RAW LLM RESPONSE:")
    print(f"  Full response: {llm_response}")

    extracted = llm_response.get("extracted", {})

    for field_name, value in extracted.items():
        if hasattr(session.profile, field_name):
            setattr(session.profile, field_name, value)
            print(f"  ✅ Set {field_name} = {value}")

    return {
        "response": llm_response.get("response", ""),
        "extracted": extracted,
        "is_complete": llm_response.get("is_complete", False),
        "error": llm_response.get("error", False)
    }













# """
# LLM Service for onboarding.
# Supports multiple providers: Gemini, DeepSeek
# """

# import json
# import os
# import httpx
# import logging
# import asyncio
# from typing import Optional

# from app.models import SessionData, UserProfile
# from app.questions import (
#     FIELDS,
#     FIELD_ORDER,
#     PERSONALITY,
#     COMPLETION,
#     build_fields_description,
#     get_first_question,
# )

# # === LOGGING SETUP ===
# logging.basicConfig(level=logging.DEBUG)
# logger = logging.getLogger(__name__)


# # === CONFIGURATION ===
# # Choose provider: "gemini" or "deepseek"
# LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")

# # Gemini config
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# GEMINI_MODEL = "gemini-2.0-flash"
# GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# # DeepSeek config (backup)
# DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
# DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
# DEEPSEEK_MODEL = "deepseek-chat"

# # Retry configuration
# MAX_RETRIES = 3
# RETRY_DELAY_SECONDS = 1

# logger.info(f"LLM Provider: {LLM_PROVIDER}")
# logger.info(f"Gemini API Key: {'SET' if GEMINI_API_KEY else 'NOT SET'}")
# logger.info(f"DeepSeek API Key: {'SET' if DEEPSEEK_API_KEY else 'NOT SET'}")


# # === SYSTEM PROMPT ===

# def _build_system_prompt() -> str:
#     """Build the system prompt."""
    
#     fields_desc = build_fields_description()
#     personality_rules = "\n".join([f"- {rule}" for rule in PERSONALITY["rules"]])
    
#     return f"""You are an onboarding assistant for a job platform helping job seekers find startup roles.

# ## YOUR PERSONALITY
# - Always speak as "{PERSONALITY['voice']}" (never "I" or "me")  
# - Tone: {PERSONALITY['tone']}
# - Use words like: {', '.join(PERSONALITY['style_words'])}
# - Keep messages to {PERSONALITY['message_length']}
# - Rules:
# {personality_rules}

# ## FIELDS TO COLLECT (in order)
# {fields_desc}

# ## HOW TO TRACK PROGRESS
# - Look at the conversation history to see what's already been extracted
# - Your previous responses contain "extracted" data - those fields are DONE
# - Only ask for fields that haven't been extracted yet
# - NEVER ask for information already collected in previous turns

# ## YOUR TASK EACH TURN
# 1. Extract any relevant data from the user's LATEST message
# 2. Acknowledge their answer briefly (be warm, not robotic)
# 3. Ask for the next missing field naturally
# 4. If user provided multiple pieces of info, extract ALL of them
# 5. When ALL fields are collected, set "is_complete": true

# ## RESPONSE FORMAT
# You MUST respond with valid JSON only (no markdown, no code blocks):
# {{
#     "extracted": {{
#         "field_name": "value"
#     }},
#     "response": "Your acknowledgment + next question combined naturally",
#     "is_complete": false
# }}

# IMPORTANT:
# - "extracted" should ONLY contain NEW data from the CURRENT message
# - "is_complete" is true ONLY when all 6 fields are collected
# - If nothing new to extract, use empty object: "extracted": {{}}
# - Return ONLY the JSON object, nothing else

# ## FIELD VALIDATION
# - name: Must be a real name, not gibberish or numbers
# - experience_level: Normalize to one of: Entry-level, Junior, Mid-level, Senior, Lead
#   (0-1 yrs = Entry-level, 1-2 = Junior, 3-5 = Mid-level, 5-8 = Senior, 8+ = Lead)
# - startup_stage: Must be one of: Early, Growth, Late, Unicorn

# ## WHEN COMPLETE
# When all 6 fields are collected, respond with:
# {{
#     "extracted": {{}},
#     "response": "{COMPLETION['message']}",
#     "is_complete": true
# }}
# """


# _SYSTEM_PROMPT: Optional[str] = None

# def get_system_prompt() -> str:
#     """Get cached system prompt."""
#     global _SYSTEM_PROMPT
#     if _SYSTEM_PROMPT is None:
#         _SYSTEM_PROMPT = _build_system_prompt()
#     return _SYSTEM_PROMPT


# # === VALIDATION ===

# def _validate_llm_response(content: str) -> dict:
#     """Validate and parse LLM response."""
    
#     if not content or not content.strip():
#         raise ValueError("LLM returned empty response")
    
#     content = content.strip()
    
#     # Handle markdown code blocks
#     if content.startswith("```"):
#         lines = content.splitlines()
#         if lines[0].startswith("```"):
#             lines = lines[1:]
#         if lines and lines[-1].strip() == "```":
#             lines = lines[:-1]
#         content = "\n".join(lines)
    
#     # Parse JSON
#     parsed = json.loads(content)
    
#     # Validate required fields
#     if "response" not in parsed:
#         raise ValueError("LLM response missing 'response' field")
    
#     if not parsed.get("response", "").strip():
#         raise ValueError("LLM returned empty 'response' field")
    
#     # Set defaults
#     if "extracted" not in parsed:
#         parsed["extracted"] = {}
    
#     if "is_complete" not in parsed:
#         parsed["is_complete"] = False
    
#     return parsed


# # === GEMINI API ===

# async def _call_gemini(conversation_history: list[dict]) -> dict:
#     """
#     Call Gemini API.
    
#     Gemini uses a different format than OpenAI.
#     """
    
#     system_prompt = get_system_prompt()
    
#     # Convert our format to Gemini format
#     # Gemini wants: {"role": "user", "parts": [{"text": "..."}]}
#     gemini_contents = []
    
#     # Add system prompt as first user message (Gemini doesn't have system role in same way)
#     # We'll prepend it to conversation context
    
#     for msg in conversation_history:
#         role = msg["role"]
#         # Gemini uses "user" and "model" (not "assistant")
#         if role == "assistant":
#             role = "model"
        
#         gemini_contents.append({
#             "role": role,
#             "parts": [{"text": msg["content"]}]
#         })
    
#     request_body = {
#         "contents": gemini_contents,
#         "systemInstruction": {
#             "parts": [{"text": system_prompt}]
#         },
#         "generationConfig": {
#             "temperature": 0.7,
#             "maxOutputTokens": 500,
#             "responseMimeType": "application/json"
#         }
#     }
    
#     url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
    
#     headers = {
#         "Content-Type": "application/json"
#     }

#     logger.debug(f"=== GEMINI REQUEST ===")
#     logger.debug(f"URL: {GEMINI_API_URL}")
#     logger.debug(f"Messages count: {len(gemini_contents)}")

#     async with httpx.AsyncClient(timeout=30.0) as client:
#         response = await client.post(
#             url,
#             headers=headers,
#             json=request_body
#         )
        
#         logger.debug(f"Gemini Status: {response.status_code}")
#         logger.debug(f"Gemini Response: {response.text[:500]}")
        
#         response.raise_for_status()
        
#         api_response = response.json()
        
#         # Gemini response structure:
#         # {"candidates": [{"content": {"parts": [{"text": "..."}]}}]}
        
#         if not api_response.get("candidates"):
#             raise ValueError("Gemini returned no candidates")
        
#         content = api_response["candidates"][0]["content"]["parts"][0]["text"]
#         logger.debug(f"Gemini content: {content}")
        
#         return _validate_llm_response(content)


# # === DEEPSEEK API ===

# async def _call_deepseek(conversation_history: list[dict]) -> dict:
#     """Call DeepSeek API (OpenAI-compatible)."""
    
#     system_prompt = get_system_prompt()
    
#     messages = [{"role": "system", "content": system_prompt}]
#     messages.extend(conversation_history)
    
#     request_body = {
#         "model": DEEPSEEK_MODEL,
#         "messages": messages,
#         "temperature": 0.7,
#         "max_tokens": 500,
#         "response_format": {"type": "json_object"}
#     }
    
#     headers = {
#         "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
#         "Content-Type": "application/json"
#     }

#     logger.debug(f"=== DEEPSEEK REQUEST ===")
#     logger.debug(f"Messages count: {len(messages)}")

#     async with httpx.AsyncClient(timeout=30.0) as client:
#         response = await client.post(
#             DEEPSEEK_API_URL,
#             headers=headers,
#             json=request_body
#         )
        
#         logger.debug(f"DeepSeek Status: {response.status_code}")
        
#         response.raise_for_status()
        
#         api_response = response.json()

#         if not api_response.get("choices"):
#             raise ValueError("DeepSeek returned no choices")
        
#         content = api_response["choices"][0]["message"]["content"]
        
#         return _validate_llm_response(content)


# # === UNIFIED LLM CALL WITH RETRY ===

# async def _call_llm_once(conversation_history: list[dict]) -> dict:
#     """Make a single LLM call to the configured provider."""
    
#     if LLM_PROVIDER == "gemini":
#         return await _call_gemini(conversation_history)
#     else:
#         return await _call_deepseek(conversation_history)


# async def call_llm(conversation_history: list[dict]) -> dict:
#     """Call LLM with retry logic."""
    
#     logger.info(f"Calling LLM provider: {LLM_PROVIDER}")
    
#     last_error = None
    
#     for attempt in range(MAX_RETRIES):
#         try:
#             logger.info(f"Attempt {attempt + 1}/{MAX_RETRIES}")
            
#             result = await _call_llm_once(conversation_history)
            
#             logger.info(f"Success on attempt {attempt + 1}")
#             logger.info(f"Extracted: {result.get('extracted', {})}")
            
#             return result
            
#         except httpx.HTTPStatusError as e:
#             last_error = e
#             logger.warning(f"HTTP error: {e.response.status_code} - {e.response.text[:200]}")
            
#             if e.response.status_code in [401, 403]:
#                 logger.error("Authentication error - not retrying")
#                 break
                
#         except (json.JSONDecodeError, ValueError) as e:
#             last_error = e
#             logger.warning(f"Parse error: {e}")
            
#         except Exception as e:
#             last_error = e
#             logger.warning(f"Unexpected error: {type(e).__name__}: {e}")
        
#         if attempt < MAX_RETRIES - 1:
#             delay = RETRY_DELAY_SECONDS * (2 ** attempt)
#             logger.info(f"Waiting {delay}s before retry...")
#             await asyncio.sleep(delay)
    
#     logger.error(f"All {MAX_RETRIES} attempts failed. Last error: {last_error}")
#     return _fallback_response("We're having trouble connecting. Could you try that again?")


# def _fallback_response(message: str) -> dict:
#     """Return safe fallback response."""
#     return {
#         "extracted": {},
#         "response": message,
#         "is_complete": False,
#         "error": True
#     }


# # === MAIN PROCESSING ===

# async def process_message(session: SessionData, user_message: str) -> dict:
#     """Process a user message and return the next response."""
    
#     conversation_history = [
#         {"role": msg["role"], "content": msg["content"]}
#         for msg in session.conversation_history
#     ]
    
#     conversation_history.append({
#         "role": "user",
#         "content": user_message
#     })
    
#     llm_response = await call_llm(conversation_history)
    
#     extracted = llm_response.get("extracted", {})
    
#     for field_name, value in extracted.items():
#         if hasattr(session.profile, field_name):
#             setattr(session.profile, field_name, value)
    
#     return {
#         "response": llm_response.get("response", ""),
#         "extracted": extracted,
#         "is_complete": llm_response.get("is_complete", False),
#         "error": llm_response.get("error", False)
#     }




































# """
# LLM Service for onboarding.
# Handles AI-powered question generation and data extraction.
# Production-grade with retry logic and validation.
# """

# import json
# import os
# import httpx
# import logging
# import asyncio
# from typing import Optional

# from app.models import SessionData, UserProfile
# from app.questions import (
#     FIELDS,
#     FIELD_ORDER,
#     PERSONALITY,
#     COMPLETION,
#     build_fields_description,
#     get_first_question,
# )

# # === LOGGING SETUP ===
# logging.basicConfig(level=logging.DEBUG)
# logger = logging.getLogger(__name__)


# # === CONFIGURATION ===
# DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
# DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
# DEEPSEEK_MODEL = "deepseek-chat"

# # Retry configuration
# MAX_RETRIES = 3
# RETRY_DELAY_SECONDS = 1  # Will exponentially increase

# logger.info(f"DeepSeek URL: {DEEPSEEK_API_URL}")
# logger.info(f"DeepSeek API Key: {'SET' if DEEPSEEK_API_KEY else 'NOT SET'}")
# logger.info(f"DeepSeek Model: {DEEPSEEK_MODEL}")


# # === STATIC SYSTEM PROMPT ===

# def _build_system_prompt() -> str:
#     """Build the static system prompt."""
    
#     fields_desc = build_fields_description()
#     personality_rules = "\n".join([f"- {rule}" for rule in PERSONALITY["rules"]])
    
#     return f"""You are an onboarding assistant for a job platform helping job seekers find startup roles.

# ## YOUR PERSONALITY
# - Always speak as "{PERSONALITY['voice']}" (never "I" or "me")  
# - Tone: {PERSONALITY['tone']}
# - Use words like: {', '.join(PERSONALITY['style_words'])}
# - Keep messages to {PERSONALITY['message_length']}
# - Rules:
# {personality_rules}

# ## FIELDS TO COLLECT (in order)
# {fields_desc}

# ## HOW TO TRACK PROGRESS
# - Look at the conversation history to see what's already been extracted
# - Your previous responses contain "extracted" data - those fields are DONE
# - Only ask for fields that haven't been extracted yet
# - NEVER ask for information already collected in previous turns

# ## YOUR TASK EACH TURN
# 1. Extract any relevant data from the user's LATEST message
# 2. Acknowledge their answer briefly (be warm, not robotic)
# 3. Ask for the next missing field naturally
# 4. If user provided multiple pieces of info, extract ALL of them
# 5. When ALL fields are collected, set "is_complete": true

# ## RESPONSE FORMAT
# You MUST respond with valid JSON only:
# {{
#     "extracted": {{
#         "field_name": "value"
#     }},
#     "response": "Your acknowledgment + next question combined naturally",
#     "is_complete": false
# }}

# IMPORTANT:
# - "extracted" should ONLY contain NEW data from the CURRENT message
# - "is_complete" is true ONLY when all 6 fields are collected
# - If nothing new to extract, use empty object: "extracted": {{}}

# ## FIELD VALIDATION
# - name: Must be a real name, not gibberish or numbers
# - experience_level: Normalize to one of: Entry-level, Junior, Mid-level, Senior, Lead
#   (0-1 yrs = Entry-level, 1-2 = Junior, 3-5 = Mid-level, 5-8 = Senior, 8+ = Lead)
# - startup_stage: Must be one of: Early, Growth, Late, Unicorn

# ## WHEN COMPLETE
# When all 6 fields are collected, respond with:
# {{
#     "extracted": {{}},
#     "response": "{COMPLETION['message']}",
#     "is_complete": true
# }}
# """


# # Cache the system prompt
# _SYSTEM_PROMPT: Optional[str] = None

# def get_system_prompt() -> str:
#     """Get cached system prompt."""
#     global _SYSTEM_PROMPT
#     if _SYSTEM_PROMPT is None:
#         _SYSTEM_PROMPT = _build_system_prompt()
#     return _SYSTEM_PROMPT


# # === VALIDATION ===

# def _validate_llm_response(content: str) -> dict:
#     """
#     Validate and parse LLM response.
#     Raises ValueError if response is invalid.
#     """
    
#     # Check for empty/whitespace response
#     if not content or not content.strip():
#         raise ValueError("LLM returned empty response")
    
#     content = content.strip()
    
#     # Handle markdown code blocks
#     if content.startswith("```"):
#         lines = content.splitlines()
#         if lines[0].startswith("```"):
#             lines = lines[1:]
#         if lines and lines[-1].strip() == "```":
#             lines = lines[:-1]
#         content = "\n".join(lines)
    
#     # Parse JSON
#     parsed = json.loads(content)
    
#     # Validate required fields
#     if "response" not in parsed:
#         raise ValueError("LLM response missing 'response' field")
    
#     if not parsed.get("response", "").strip():
#         raise ValueError("LLM returned empty 'response' field")
    
#     # Ensure extracted is a dict
#     if "extracted" not in parsed:
#         parsed["extracted"] = {}
    
#     # Ensure is_complete is boolean
#     if "is_complete" not in parsed:
#         parsed["is_complete"] = False
    
#     return parsed


# # === LLM API CALL WITH RETRY ===

# async def _call_llm_once(messages: list[dict]) -> dict:
#     """
#     Make a single LLM API call.
#     Returns parsed response or raises exception.
#     """
    
#     request_body = {
#         "model": DEEPSEEK_MODEL,
#         "messages": messages,
#         "temperature": 0.7,
#         "max_tokens": 500,
#         "response_format": {"type": "json_object"}
#     }
    
#     headers = {
#         "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
#         "Content-Type": "application/json"
#     }

#     async with httpx.AsyncClient(timeout=30.0) as client:
#         response = await client.post(
#             DEEPSEEK_API_URL,
#             headers=headers,
#             json=request_body
#         )
        
#         logger.debug(f"LLM Status: {response.status_code}")
        
#         response.raise_for_status()
        
#         api_response = response.json()

#         if not api_response.get("choices"):
#             raise ValueError("API returned no choices")
        
#         content_str = api_response["choices"][0]["message"]["content"]
#         logger.debug(f"LLM raw content: {content_str[:200]}")
        
#         # Validate and parse
#         return _validate_llm_response(content_str)


# async def call_llm(conversation_history: list[dict]) -> dict:
#     """
#     Call the DeepSeek API with retry logic.
    
#     Retries up to MAX_RETRIES times with exponential backoff.
#     """
    
#     system_prompt = get_system_prompt()
    
#     messages = [{"role": "system", "content": system_prompt}]
#     messages.extend(conversation_history)
    
#     logger.debug(f"=== LLM REQUEST ===")
#     logger.debug(f"Messages count: {len(messages)}")
    
#     last_error = None
    
#     for attempt in range(MAX_RETRIES):
#         try:
#             logger.info(f"LLM attempt {attempt + 1}/{MAX_RETRIES}")
            
#             result = await _call_llm_once(messages)
            
#             logger.info(f"LLM success on attempt {attempt + 1}")
#             logger.info(f"Extracted: {result.get('extracted', {})}")
            
#             return result
            
#         except httpx.HTTPStatusError as e:
#             last_error = e
#             logger.warning(f"HTTP error on attempt {attempt + 1}: {e.response.status_code}")
            
#             # Don't retry on auth errors
#             if e.response.status_code in [401, 403]:
#                 logger.error("Authentication error - not retrying")
#                 break
                
#         except (json.JSONDecodeError, ValueError) as e:
#             last_error = e
#             logger.warning(f"Parse error on attempt {attempt + 1}: {e}")
            
#         except Exception as e:
#             last_error = e
#             logger.warning(f"Unexpected error on attempt {attempt + 1}: {e}")
        
#         # Wait before retry (exponential backoff)
#         if attempt < MAX_RETRIES - 1:
#             delay = RETRY_DELAY_SECONDS * (2 ** attempt)  # 1s, 2s, 4s
#             logger.info(f"Waiting {delay}s before retry...")
#             await asyncio.sleep(delay)
    
#     # All retries failed
#     logger.error(f"All {MAX_RETRIES} attempts failed. Last error: {last_error}")
#     return _fallback_response("We're having trouble connecting. Could you try that again?")


# def _fallback_response(message: str) -> dict:
#     """Return a safe fallback response."""
#     return {
#         "extracted": {},
#         "response": message,
#         "is_complete": False,
#         "error": True
#     }


# # === MAIN PROCESSING ===

# async def process_message(session: SessionData, user_message: str) -> dict:
#     """
#     Process a user message and return the next response.
#     """
    
#     # Build conversation history for LLM
#     conversation_history = [
#         {"role": msg["role"], "content": msg["content"]}
#         for msg in session.conversation_history
#     ]
    
#     # Add the new user message
#     conversation_history.append({
#         "role": "user",
#         "content": user_message
#     })
    
#     # Call LLM with retry
#     llm_response = await call_llm(conversation_history)
    
#     # Update profile with extracted data
#     extracted = llm_response.get("extracted", {})
    
#     for field_name, value in extracted.items():
#         if hasattr(session.profile, field_name):
#             setattr(session.profile, field_name, value)
    
#     return {
#         "response": llm_response.get("response", ""),
#         "extracted": extracted,
#         "is_complete": llm_response.get("is_complete", False),
#         "error": llm_response.get("error", False)
#     }
# # ```

# # ---

# # ## What We Added

# # | Feature | What It Does |
# # |---------|--------------|
# # | `_validate_llm_response()` | Checks for empty/whitespace BEFORE parsing |
# # | `MAX_RETRIES = 3` | Try up to 3 times |
# # | `Exponential backoff` | Wait 1s, 2s, 4s between retries |
# # | `Separate _call_llm_once()` | Clean separation of single call vs retry logic |
# # | `Don't retry auth errors` | 401/403 won't get better with retries |
# # | `Better logging` | Shows which attempt succeeded/failed |

# # ---

# # ## How It Works Now
# # ```
# # User sends answer
# #        │
# #        ▼
# # ┌─────────────────┐
# # │ Attempt 1       │──── Success ───▶ Return response
# # └────────┬────────┘
# #          │ Fail (empty/error)
# #          ▼
# #     Wait 1 second
# #          │
# #          ▼
# # ┌─────────────────┐
# # │ Attempt 2       │──── Success ───▶ Return response
# # └────────┬────────┘
# #          │ Fail
# #          ▼
# #     Wait 2 seconds
# #          │
# #          ▼
# # ┌─────────────────┐
# # │ Attempt 3       │──── Success ───▶ Return response
# # └────────┬────────┘
# #          │ Fail
# #          ▼
# #    Return fallback:
# #    "We're having trouble..."