# Database Schema Design

## Overview

This document defines the database schema for the onboarding system. We're using PostgreSQL with SQLAlchemy ORM.

---

## Table Summary

| Table Name | Purpose | Records (10K users) |
|------------|---------|---------------------|
| **users** | Core user entity | 10,000 |
| **onboarding_sessions** | Track onboarding attempts | 10,000-15,000 |
| **user_profiles** | Collected onboarding data | 10,000 |
| **conversation_messages** | Full chat history | 100,000 |

**Total Storage: ~100MB for 10K users**

---

## Table 1: `users`

### Purpose
Central user entity. Currently minimal, but designed for future extension (email, auth, etc.)

### Schema

```sql
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Optional fields (for future use)
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    deleted_at TIMESTAMP,  -- Soft delete

    -- Metadata
    source VARCHAR(100),  -- Where user came from (e.g., 'web', 'mobile', 'referral')
    metadata JSONB DEFAULT '{}'  -- Flexible storage for future fields
);

-- Indexes
CREATE INDEX idx_users_email ON users(email) WHERE email IS NOT NULL;
CREATE INDEX idx_users_created_at ON users(created_at);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = TRUE;
```

### Fields Explained

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | UUID | Yes | Primary identifier (auto-generated) |
| `created_at` | TIMESTAMP | Yes | When user was created |
| `updated_at` | TIMESTAMP | Yes | Last update time |
| `email` | VARCHAR | No | Email (for future auth) |
| `phone` | VARCHAR | No | Phone (for future auth) |
| `is_active` | BOOLEAN | Yes | Soft deletion flag |
| `deleted_at` | TIMESTAMP | No | When user was deleted (GDPR) |
| `source` | VARCHAR | No | User acquisition source |
| `metadata` | JSONB | No | Flexible JSON storage |

### Sample Data

```json
{
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2025-12-11T10:30:00Z",
    "updated_at": "2025-12-11T10:30:00Z",
    "email": null,
    "phone": null,
    "is_active": true,
    "deleted_at": null,
    "source": "web",
    "metadata": {}
}
```

---

## Table 2: `onboarding_sessions`

### Purpose
Track each onboarding attempt. Users may restart onboarding, so there can be multiple sessions per user.

### Schema

```sql
CREATE TABLE onboarding_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Status tracking
    status VARCHAR(50) NOT NULL DEFAULT 'in_progress',
    -- Possible values: 'in_progress', 'completed', 'abandoned'

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,

    -- Metadata
    llm_provider_used VARCHAR(50),  -- 'openai', 'gemini', 'deepseek'
    total_messages_count INTEGER DEFAULT 0,

    -- Analytics fields
    ip_address INET,
    user_agent TEXT,

    CONSTRAINT valid_status CHECK (status IN ('in_progress', 'completed', 'abandoned'))
);

-- Indexes
CREATE INDEX idx_sessions_user_id ON onboarding_sessions(user_id);
CREATE INDEX idx_sessions_status ON onboarding_sessions(status);
CREATE INDEX idx_sessions_created_at ON onboarding_sessions(created_at);
CREATE INDEX idx_sessions_completed_at ON onboarding_sessions(completed_at)
    WHERE completed_at IS NOT NULL;
```

### Fields Explained

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | UUID | Yes | Unique session identifier |
| `user_id` | UUID | Yes | Foreign key to users table |
| `status` | VARCHAR | Yes | Current session status (enum) |
| `created_at` | TIMESTAMP | Yes | Session start time |
| `updated_at` | TIMESTAMP | Yes | Last activity time |
| `completed_at` | TIMESTAMP | No | When session finished |
| `llm_provider_used` | VARCHAR | No | Which LLM was used |
| `total_messages_count` | INTEGER | Yes | Total messages exchanged |
| `ip_address` | INET | No | User's IP (for fraud detection) |
| `user_agent` | TEXT | No | Browser/device info |

### Status Lifecycle

```
in_progress → completed (user finishes all fields)
              ↓
           abandoned (user quits mid-way)
```

### Sample Data

```json
{
    "session_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "completed",
    "created_at": "2025-12-11T10:30:00Z",
    "updated_at": "2025-12-11T10:34:30Z",
    "completed_at": "2025-12-11T10:34:30Z",
    "llm_provider_used": "openai",
    "total_messages_count": 8,
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0..."
}
```

---

## Table 3: `user_profiles`

### Purpose
Store the actual onboarding data collected from users. This is your product data.

### Schema

```sql
CREATE TABLE user_profiles (
    profile_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES onboarding_sessions(session_id) ON DELETE CASCADE,

    -- Collected fields (matching your FIELD_ORDER)
    name VARCHAR(255) NOT NULL,
    role VARCHAR(255) NOT NULL,
    experience_level VARCHAR(50) NOT NULL,
    location VARCHAR(255) NOT NULL,
    startup_stage VARCHAR(50) NOT NULL,
    extra_preferences TEXT,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Validation
    CONSTRAINT valid_experience_level CHECK (
        experience_level IN ('Entry-level', 'Junior', 'Mid-level', 'Senior', 'Lead')
    ),
    CONSTRAINT valid_startup_stage CHECK (
        startup_stage IN ('Early', 'Growth', 'Late', 'Unicorn')
    )
);

-- Indexes
CREATE INDEX idx_profiles_user_id ON user_profiles(user_id);
CREATE INDEX idx_profiles_session_id ON user_profiles(session_id);
CREATE INDEX idx_profiles_role ON user_profiles(role);
CREATE INDEX idx_profiles_experience_level ON user_profiles(experience_level);
CREATE INDEX idx_profiles_location ON user_profiles(location);
CREATE INDEX idx_profiles_startup_stage ON user_profiles(startup_stage);
```

### Fields Explained

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `profile_id` | UUID | Yes | Primary key |
| `user_id` | UUID | Yes | Foreign key (UNIQUE - one profile per user) |
| `session_id` | UUID | Yes | Which session created this profile |
| `name` | VARCHAR | Yes | User's full name |
| `role` | VARCHAR | Yes | Target job role(s) |
| `experience_level` | VARCHAR | Yes | Seniority level (normalized) |
| `location` | VARCHAR | Yes | Preferred work location |
| `startup_stage` | VARCHAR | Yes | Preferred startup stage |
| `extra_preferences` | TEXT | No | Additional preferences/notes |
| `created_at` | TIMESTAMP | Yes | When profile was created |
| `updated_at` | TIMESTAMP | Yes | Last update time |

### Sample Data

```json
{
    "profile_id": "9b3d4c5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "session_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "name": "Rahul Sharma",
    "role": "Backend Developer",
    "experience_level": "Mid-level",
    "location": "Bangalore",
    "startup_stage": "Growth",
    "extra_preferences": "Interested in fintech, prefers remote-first companies",
    "created_at": "2025-12-11T10:34:30Z",
    "updated_at": "2025-12-11T10:34:30Z"
}
```

---

## Table 4: `conversation_messages`

### Purpose
Store full conversation history for debugging, analytics, and future training.

### Schema

```sql
CREATE TABLE conversation_messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES onboarding_sessions(session_id) ON DELETE CASCADE,

    -- Message content
    role VARCHAR(20) NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,

    -- Timestamp
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),

    -- LLM metadata (for assistant messages only)
    extracted_fields JSONB,  -- What fields were extracted: {"name": "John"}
    llm_metadata JSONB,      -- Tokens used, latency, model, etc.

    -- Validation
    CONSTRAINT valid_role CHECK (role IN ('user', 'assistant'))
);

-- Indexes
CREATE INDEX idx_messages_session_id ON conversation_messages(session_id);
CREATE INDEX idx_messages_timestamp ON conversation_messages(timestamp);
CREATE INDEX idx_messages_role ON conversation_messages(role);
CREATE INDEX idx_messages_extracted_fields ON conversation_messages USING GIN (extracted_fields)
    WHERE extracted_fields IS NOT NULL;
```

### Fields Explained

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message_id` | UUID | Yes | Unique message identifier |
| `session_id` | UUID | Yes | Which session this belongs to |
| `role` | VARCHAR | Yes | 'user' or 'assistant' |
| `content` | TEXT | Yes | Message text |
| `timestamp` | TIMESTAMP | Yes | When message was sent |
| `extracted_fields` | JSONB | No | Fields extracted by LLM |
| `llm_metadata` | JSONB | No | LLM performance data |

### Sample Data

**User Message:**
```json
{
    "message_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "session_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "role": "user",
    "content": "My name is Rahul Sharma and I'm looking for Backend Developer roles",
    "timestamp": "2025-12-11T10:30:15Z",
    "extracted_fields": null,
    "llm_metadata": null
}
```

**Assistant Message:**
```json
{
    "message_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "session_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "role": "assistant",
    "content": "Nice to meet you, Rahul! How many years of experience do you have?",
    "timestamp": "2025-12-11T10:30:18Z",
    "extracted_fields": {
        "name": "Rahul Sharma",
        "role": "Backend Developer"
    },
    "llm_metadata": {
        "provider": "openai",
        "model": "gpt-4o",
        "tokens_used": 450,
        "latency_ms": 1200,
        "cost_usd": 0.0015
    }
}
```

---

## Entity Relationships

```
users (1) ──────── (N) onboarding_sessions
  │                          │
  │                          │
  │(1)                      (1)
  │                          │
  └──── (1) user_profiles (1)┘
                │
                │ (1)
                │
                └──── (N) conversation_messages
```

**Explained:**
- One user has many sessions (can restart onboarding)
- One user has one profile (latest session wins)
- One session has many messages
- One profile links back to the session that created it

---

## Database Initialization SQL

```sql
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create tables in order (respecting foreign keys)
-- 1. Users (no dependencies)
CREATE TABLE users (...);

-- 2. Sessions (depends on users)
CREATE TABLE onboarding_sessions (...);

-- 3. Profiles (depends on users and sessions)
CREATE TABLE user_profiles (...);

-- 4. Messages (depends on sessions)
CREATE TABLE conversation_messages (...);

-- Create all indexes
-- (see individual table definitions above)
```

---

## Data Flow Example

### User completes onboarding:

1. **POST /api/onboarding/start**
   ```
   → Create record in `users` (if new user_id)
   → Create record in `onboarding_sessions` (status='in_progress')
   → Create first message in `conversation_messages` (role='assistant')
   ```

2. **POST /api/onboarding/answer** (repeated 6-8 times)
   ```
   → Add user message to `conversation_messages`
   → Call LLM
   → Add assistant message to `conversation_messages` (with extracted_fields)
   → Update `onboarding_sessions.total_messages_count`
   ```

3. **Final POST /api/onboarding/answer** (completion)
   ```
   → Add messages to `conversation_messages`
   → Create record in `user_profiles` (all 6 fields complete)
   → Update `onboarding_sessions` (status='completed', completed_at=NOW())
   ```

---

## Key Design Decisions

### 1. **Why separate `users` and `user_profiles`?**

**Answer:** Future-proofing. Users can have authentication data (email, password) separate from their profile data. Also allows for:
- Multi-tenant systems
- User accounts without completed onboarding
- Re-onboarding without losing user identity

### 2. **Why store full `conversation_messages`?**

**Answer:** Multiple benefits:
- Debug LLM issues ("why did it extract wrong data?")
- Train future models
- Analyze where users abandon onboarding
- Compliance/audit trail
- Storage is cheap (~100MB for 10K users)

### 3. **Why JSONB for `extracted_fields` and `llm_metadata`?**

**Answer:** Flexible schema. If you:
- Add new fields in the future
- Track different LLM metrics
- Store provider-specific data

You don't need to alter the table structure.

### 4. **Why UUID instead of auto-incrementing IDs?**

**Answer:**
- Distributed systems friendly
- No sequential ID leakage
- Can generate client-side
- Better for microservices architecture later

### 5. **Why soft delete (`deleted_at`) instead of hard delete?**

**Answer:** GDPR compliance and analytics. You can:
- Mark users as deleted (stop showing data)
- Keep data for analytics (anonymized)
- Recover accidentally deleted accounts
- Maintain referential integrity

---

## Queries You'll Run Often

### Get user's onboarding status
```sql
SELECT
    u.user_id,
    s.session_id,
    s.status,
    s.created_at,
    s.completed_at,
    p.name,
    p.role
FROM users u
LEFT JOIN onboarding_sessions s ON u.user_id = s.user_id
LEFT JOIN user_profiles p ON u.user_id = p.user_id
WHERE u.user_id = $1
ORDER BY s.created_at DESC
LIMIT 1;
```

### Get session conversation history
```sql
SELECT
    role,
    content,
    extracted_fields,
    timestamp
FROM conversation_messages
WHERE session_id = $1
ORDER BY timestamp ASC;
```

### Analytics: Completion rate
```sql
SELECT
    COUNT(CASE WHEN status = 'completed' THEN 1 END) * 100.0 / COUNT(*) as completion_rate,
    AVG(EXTRACT(EPOCH FROM (completed_at - created_at))/60) as avg_duration_minutes
FROM onboarding_sessions
WHERE created_at > NOW() - INTERVAL '7 days';
```

### Analytics: Abandonment by field
```sql
WITH field_extractions AS (
    SELECT
        m.session_id,
        jsonb_object_keys(m.extracted_fields) as field_name
    FROM conversation_messages m
    WHERE m.extracted_fields IS NOT NULL
),
completed_fields AS (
    SELECT
        session_id,
        array_agg(DISTINCT field_name) as collected_fields
    FROM field_extractions
    GROUP BY session_id
)
SELECT
    CASE
        WHEN 'name' = ANY(collected_fields) THEN 'name'
        WHEN 'role' = ANY(collected_fields) THEN 'role'
        WHEN 'experience_level' = ANY(collected_fields) THEN 'experience_level'
        WHEN 'location' = ANY(collected_fields) THEN 'location'
        WHEN 'startup_stage' = ANY(collected_fields) THEN 'startup_stage'
        WHEN 'extra_preferences' = ANY(collected_fields) THEN 'extra_preferences'
        ELSE 'no_fields'
    END as last_field_collected,
    COUNT(*) as abandoned_count
FROM completed_fields cf
JOIN onboarding_sessions s ON cf.session_id = s.session_id
WHERE s.status = 'abandoned'
GROUP BY last_field_collected
ORDER BY abandoned_count DESC;
```

---

## Migration Strategy

### Phase 1: Create tables (Week 1)
```bash
# Run migration scripts
alembic upgrade head
```

### Phase 2: Dual-write (Week 2)
```python
# Write to both in-memory AND database
session = session_manager.create_session(user_id)  # In-memory
db_session = await create_db_session(user_id)      # Database
```

### Phase 3: Read from DB (Week 3)
```python
# Read from database, fallback to memory
session = await get_db_session(session_id)
if not session:
    session = session_manager.get_session(session_id)  # Fallback
```

### Phase 4: DB only (Week 4)
```python
# Remove in-memory storage completely
# All reads/writes go to PostgreSQL
```

---

## Storage Estimates

| Users | Sessions | Messages | Profiles | Total Storage |
|-------|----------|----------|----------|---------------|
| 10K | 10K | 100K | 10K | ~100MB |
| 50K | 50K | 500K | 50K | ~500MB |
| 100K | 100K | 1M | 100K | ~1GB |
| 500K | 500K | 5M | 500K | ~5GB |

---

## Next Steps

1. ✅ Review this schema (YOU ARE HERE)
2. ⬜ Create SQLAlchemy models
3. ⬜ Setup Alembic migrations
4. ⬜ Create database connection pool
5. ⬜ Refactor `app/database.py` to use PostgreSQL
6. ⬜ Add indexes for performance
7. ⬜ Write database utility functions
8. ⬜ Add transaction support

---

*Last Updated: 2025-12-11*
*Document Owner: Engineering Team*
