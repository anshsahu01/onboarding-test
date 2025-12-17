# Scaling Guide - Onboarding API

## Executive Summary

This guide covers capacity planning, metrics, and scaling strategies for handling 10K+ users with our one-time onboarding feature.

---

## Table of Contents

1. [Load Characteristics](#load-characteristics)
2. [Resource Estimation](#resource-estimation)
3. [Critical Metrics](#critical-metrics)
4. [Database Scaling](#database-scaling)
5. [LLM API Rate Limiting](#llm-api-rate-limiting)
6. [System Architecture](#system-architecture)
7. [Monitoring & Alerting](#monitoring--alerting)
8. [Failure Scenarios](#failure-scenarios)
9. [Infrastructure Recommendations](#infrastructure-recommendations)

---

## Load Characteristics

### Key Insight: One-Time Use Pattern

Since onboarding is **one-time per user**, the system has:
- Peak load during launch/marketing campaigns
- Low steady-state after initial onboarding
- No recurring daily active user spikes

### Scenario A: Gradual Growth (Organic)

```
Month 1:    500 users
Month 2:  1,000 users
Month 3:  2,000 users
Month 12: 10,000 users
```

**Peak Load:** 50-100 concurrent sessions
**Database:** Easy to handle with basic setup
**LLM Costs:** Spread over time (~$15-30/month)

### Scenario B: Spike Launch (Marketing Campaign)

```
Day 1:  5,000 users
Week 1: 8,000 users
Week 2: 10,000 users
```

**Peak Load:** 500-1,000 concurrent sessions
**Database:** Need connection pooling + monitoring
**LLM Costs:** High upfront ($150-500 in first week)

---

## Resource Estimation

### Per User Session Breakdown

| Resource | Per User | 10K Users Total |
|----------|----------|-----------------|
| **Messages Exchanged** | 8-12 messages | 100,000 messages |
| **LLM API Calls** | 6-8 calls | 70,000 LLM calls |
| **Session Duration** | 3-5 minutes | 500-800 hours total |
| **DB Records Created** | 1 session + 1 profile + 10 msgs | 10K sessions, 100K messages |
| **Storage Used** | ~10KB per session | ~100MB total |

### Single Session LLM Token Usage

```
Per onboarding session (6 fields):
- 6-8 LLM API calls
- ~500 tokens input per call (system prompt + history)
- ~150 tokens output per call
- Total: ~3,900 tokens per user
```

### Cost Estimation

#### OpenAI GPT-4o
```
Pricing:
- Input:  $2.50 per 1M tokens
- Output: $10.00 per 1M tokens

Per user calculation:
- Input:  3,000 tokens × $2.50/1M = $0.0075
- Output:   900 tokens × $10.00/1M = $0.0090
- Total per user: ~$0.0165

10K users = $165
```

#### Gemini / DeepSeek
```
~10x cheaper than GPT-4o
10K users = $15-30
```

---

## Critical Metrics

### 1. User Experience Metrics (Product)

| Metric | Description | Target | Priority |
|--------|-------------|--------|----------|
| **Completion Rate** | % users who finish onboarding | >85% | HIGH |
| **Time to Complete** | Average session duration | <5 min | HIGH |
| **Abandonment Point** | Field where users quit | Track all | HIGH |
| **Average Messages** | Conversation efficiency | <10 msgs | MEDIUM |
| **Error Rate** | Failed sessions due to errors | <1% | HIGH |

**SQL Queries:**

```sql
-- Completion rate (last 30 days)
SELECT
  COUNT(CASE WHEN status = 'completed' THEN 1 END) * 100.0 / COUNT(*) as completion_rate
FROM onboarding_sessions
WHERE created_at > NOW() - INTERVAL '30 days';

-- Average completion time
SELECT
  AVG(EXTRACT(EPOCH FROM (completed_at - created_at))/60) as avg_minutes
FROM onboarding_sessions
WHERE status = 'completed';

-- Abandonment analysis
SELECT
  abandonment_at_field,
  COUNT(*) as count,
  COUNT(*) * 100.0 / (SELECT COUNT(*) FROM session_analytics WHERE abandonment_at_field IS NOT NULL) as percentage
FROM session_analytics
WHERE abandonment_at_field IS NOT NULL
GROUP BY abandonment_at_field
ORDER BY count DESC;

-- Messages per session distribution
SELECT
  bucket,
  COUNT(*) as sessions
FROM (
  SELECT
    session_id,
    CASE
      WHEN total_messages_count < 8 THEN '<8 messages'
      WHEN total_messages_count BETWEEN 8 AND 10 THEN '8-10 messages'
      WHEN total_messages_count BETWEEN 11 AND 15 THEN '11-15 messages'
      ELSE '>15 messages'
    END as bucket
  FROM onboarding_sessions
  WHERE status = 'completed'
) AS bucketed
GROUP BY bucket
ORDER BY bucket;
```

### 2. System Performance Metrics (Engineering)

| Metric | Description | Target | Alert Threshold |
|--------|-------------|--------|-----------------|
| **API Response Time (P95)** | 95th percentile response | <2s | >3s |
| **LLM Latency (P95)** | LLM API call duration | <3s | >5s |
| **Database Query Time (P95)** | DB query performance | <100ms | >500ms |
| **Concurrent Sessions** | Active sessions now | Monitor | >50 |
| **Error Rate** | Failed requests / total | <1% | >2% |

**Python Logging Implementation:**

```python
import time
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Middleware for request timing
@app.middleware("http")
async def add_timing_header(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000

    logger.info(json.dumps({
        "event": "api_request",
        "path": request.url.path,
        "method": request.method,
        "duration_ms": round(duration_ms, 2),
        "status_code": response.status_code,
        "timestamp": datetime.utcnow().isoformat()
    }))

    return response
```

### 3. Cost Metrics (Business)

| Metric | 10K Users | 50K Users | 100K Users |
|--------|-----------|-----------|------------|
| **LLM Cost (GPT-4o)** | $165 | $825 | $1,650 |
| **LLM Cost (Gemini)** | $20 | $100 | $200 |
| **Database (DigitalOcean)** | $12/mo | $24/mo | $40/mo |
| **Storage** | <1GB | ~2GB | ~5GB |
| **Total (one-time)** | ~$185 | ~$850 | ~$1,690 |

**Cost per Completed Onboarding:** $0.015 - $0.06

### 4. Data Quality Metrics (AI/ML)

| Metric | Description | Target | Action If Below |
|--------|-------------|--------|-----------------|
| **Field Extraction Accuracy** | Correct field parsing | >95% | Review system prompt |
| **Re-ask Rate** | Asking same field twice | <5% | Improve LLM memory |
| **Validation Failure Rate** | Invalid data extracted | <2% | Add validation rules |
| **Fallback Rate** | LLM failures needing retry | <3% | Check API health |

**Tracking Code:**

```python
# In services.py after LLM extraction
def track_extraction_quality(session, extracted_fields):
    already_collected = get_collected_field(session.profile)

    # Detect re-asks (same field asked twice)
    re_asked = set(extracted_fields.keys()) & set(already_collected.keys())
    if re_asked:
        logger.warning(json.dumps({
            "event": "llm_re_asked_field",
            "session_id": session.session_id,
            "fields": list(re_asked),
            "timestamp": datetime.utcnow().isoformat()
        }))

    # Track extraction success
    logger.info(json.dumps({
        "event": "fields_extracted",
        "session_id": session.session_id,
        "fields_extracted": list(extracted_fields.keys()),
        "total_fields_collected": len(already_collected) + len(extracted_fields),
        "timestamp": datetime.utcnow().isoformat()
    }))
```

---

## Database Scaling

### Storage Requirements

| Component | 10K Users | 50K Users | 100K Users |
|-----------|-----------|-----------|------------|
| **Users table** | 5MB | 25MB | 50MB |
| **Sessions table** | 10MB | 50MB | 100MB |
| **Profiles table** | 20MB | 100MB | 200MB |
| **Messages table** | 100MB | 500MB | 1GB |
| **Analytics table** | 20MB | 100MB | 200MB |
| **Indexes (50% overhead)** | 80MB | 390MB | 775MB |
| **Total** | ~235MB | ~1.2GB | ~2.3GB |

**Conclusion:** Current DigitalOcean droplet handles 100K+ users easily.

### Connection Pooling Configuration

```python
# app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,          # 10 permanent connections
    max_overflow=20,       # Up to 30 total connections during spikes
    pool_timeout=30,       # Wait 30s for connection before failing
    pool_recycle=3600,     # Recycle connections every hour
    pool_pre_ping=True,    # Verify connections before using
    echo=False,            # Disable SQL logging in production (set True for debug)
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

**Why these settings?**

- **pool_size=10**: Handle 10 concurrent sessions comfortably
- **max_overflow=20**: Burst to 30 total connections during spikes
- **pool_recycle=3600**: Prevent stale connections
- **pool_pre_ping=True**: Auto-reconnect on database restarts

### When to Scale Up Database

| Indicator | Threshold | Action |
|-----------|-----------|--------|
| **Concurrent sessions** | >100 active | Increase pool_size to 20-30 |
| **Database CPU** | >80% sustained | Add indexes, optimize queries |
| **Storage** | >80% full | Upgrade droplet storage tier |
| **Memory usage** | >90% | Upgrade RAM or reduce pool_size |
| **Query latency** | P95 >500ms | Add missing indexes, use EXPLAIN |

### Essential Indexes

```sql
-- Session lookups
CREATE INDEX idx_sessions_user_id ON onboarding_sessions(user_id);
CREATE INDEX idx_sessions_status ON onboarding_sessions(status);
CREATE INDEX idx_sessions_created_at ON onboarding_sessions(created_at);

-- Message lookups
CREATE INDEX idx_messages_session_id ON conversation_messages(session_id);
CREATE INDEX idx_messages_timestamp ON conversation_messages(timestamp);

-- Profile lookups
CREATE INDEX idx_profiles_user_id ON user_profiles(user_id);

-- Analytics queries
CREATE INDEX idx_analytics_session_id ON session_analytics(session_id);
CREATE INDEX idx_sessions_completed_at ON onboarding_sessions(completed_at)
    WHERE status = 'completed';
```

---

## LLM API Rate Limiting

### OpenAI Rate Limits by Tier

| Tier | Spend Required | RPM (Requests/Min) | TPM (Tokens/Min) | Concurrent Sessions |
|------|----------------|-------------------|------------------|---------------------|
| **Tier 1** | $5 | 500 | 30,000 | ~45 sessions |
| **Tier 2** | $50 | 5,000 | 450,000 | ~450 sessions |
| **Tier 3** | $500 | 10,000 | 1,000,000 | ~900 sessions |
| **Tier 4** | $5,000 | 80,000 | 10,000,000 | ~7,200 sessions |

**Your Usage per Session:**
- 6-8 LLM requests
- ~3,900 tokens total
- ~650 tokens per request

**Tier 1 Capacity (Default):**
```
500 RPM / 6 requests per session = ~83 sessions/min
30,000 TPM / 650 tokens per request = ~46 requests/min = ~7 sessions/min

ACTUAL BOTTLENECK: ~45 concurrent sessions max
```

**What This Means:**
- **10K users over 1 month**: No problem (330/day = 14/hour)
- **1K users in 1 hour (spike)**: Will hit rate limits

### Mitigation Strategy 1: Multi-Provider Load Balancing

```python
# app/config.py
LLM_PROVIDERS = {
    "openai": {
        "weight": 40,  # 40% of traffic
        "rpm_limit": 500,
        "enabled": True
    },
    "gemini": {
        "weight": 40,  # 40% of traffic
        "rpm_limit": 1000,
        "enabled": True
    },
    "deepseek": {
        "weight": 20,  # 20% of traffic
        "rpm_limit": 500,
        "enabled": True
    }
}

# app/services.py
import random

def select_provider():
    """Select LLM provider based on weights"""
    providers = []
    for name, config in LLM_PROVIDERS.items():
        if config["enabled"]:
            providers.extend([name] * config["weight"])

    return random.choice(providers)

async def call_llm_with_fallback(conversation_history):
    """Call LLM with automatic fallback"""
    primary_provider = select_provider()

    try:
        return await call_llm(conversation_history, provider=primary_provider)
    except RateLimitError:
        logger.warning(f"Rate limit hit on {primary_provider}, trying fallback")

        # Try other providers
        for provider in ["openai", "gemini", "deepseek"]:
            if provider != primary_provider and LLM_PROVIDERS[provider]["enabled"]:
                try:
                    return await call_llm(conversation_history, provider=provider)
                except Exception as e:
                    logger.warning(f"Fallback {provider} failed: {e}")
                    continue

        raise Exception("All LLM providers failed")
```

**Benefit:** 3x rate limit capacity (500 + 1000 + 500 = 2000 RPM)

### Mitigation Strategy 2: Queue System (Redis)

```python
# app/queue.py
from redis import Redis
from rq import Queue
import os

redis_conn = Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True
)

llm_queue = Queue("llm_requests", connection=redis_conn)

# Enqueue LLM calls during high load
def enqueue_llm_call(session_id, user_message):
    job = llm_queue.enqueue(
        process_message_job,
        session_id=session_id,
        user_message=user_message,
        job_timeout=60
    )
    return job.id

# Worker processes queue respecting rate limits
# Run: rq worker llm_requests --with-scheduler
```

**When to use:**
- During traffic spikes (>50 concurrent sessions)
- When LLM rate limit errors occur
- For non-real-time processing acceptable to users

### Mitigation Strategy 3: Request Throttling

```python
# app/middleware.py
from fastapi import HTTPException
from datetime import datetime, timedelta
import asyncio

# Simple in-memory rate limiter (use Redis for production)
request_counts = {}

async def rate_limit_middleware(request, call_next):
    client_ip = request.client.host
    now = datetime.utcnow()

    # Clean old entries
    request_counts = {
        ip: [ts for ts in timestamps if now - ts < timedelta(minutes=1)]
        for ip, timestamps in request_counts.items()
    }

    # Check rate
    if client_ip not in request_counts:
        request_counts[client_ip] = []

    if len(request_counts[client_ip]) >= 30:  # 30 requests per minute per IP
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    request_counts[client_ip].append(now)

    return await call_next(request)
```

---

## System Architecture

### Current Architecture (Single Instance)

```
┌─────────────────────────────────────────┐
│           Client (Browser/App)          │
└──────────────────┬──────────────────────┘
                   │ HTTPS
                   ▼
┌─────────────────────────────────────────┐
│         FastAPI Application             │
│  (Single instance on DO Droplet)        │
│                                         │
│  ┌─────────────┐    ┌──────────────┐  │
│  │  main.py    │    │  services.py │  │
│  │  (routes)   │───▶│  (LLM calls) │  │
│  └─────────────┘    └──────────────┘  │
│                                         │
│  ┌─────────────┐    ┌──────────────┐  │
│  │ database.py │    │  models.py   │  │
│  │ (session    │    │  (Pydantic)  │  │
│  │  manager)   │    │              │  │
│  └──────┬──────┘    └──────────────┘  │
└─────────┼──────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────┐
│      PostgreSQL (Same Droplet)          │
│      - Sessions, Profiles, Messages     │
└─────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────┐
│       LLM APIs (External)               │
│  - OpenAI GPT-4o                        │
│  - Google Gemini                        │
│  - DeepSeek                             │
└─────────────────────────────────────────┘
```

**Good for:** 0-50K users

### Scaled Architecture (50K+ users)

```
                    ┌──────────────────┐
                    │  Load Balancer   │
                    │  (Nginx/HAProxy) │
                    └────────┬─────────┘
                             │
              ┏━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━┓
              ▼                              ▼
    ┌──────────────────┐          ┌──────────────────┐
    │  FastAPI App 1   │          │  FastAPI App 2   │
    │  (Primary)       │          │  (Replica)       │
    └────────┬─────────┘          └────────┬─────────┘
             │                              │
             └──────────────┬───────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         ▼                  ▼                  ▼
┌────────────────┐  ┌──────────────┐  ┌──────────────┐
│  PostgreSQL    │  │    Redis     │  │   Monitoring │
│  (Managed DB)  │  │  - Cache     │  │  - Grafana   │
│  - Primary     │  │  - Sessions  │  │  - Prometheus│
│  - Replica     │  │  - Queues    │  │              │
└────────────────┘  └──────────────┘  └──────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│       LLM APIs (Multi-provider)         │
│  - OpenAI (primary)                     │
│  - Gemini (fallback)                    │
│  - DeepSeek (fallback)                  │
└─────────────────────────────────────────┘
```

**Good for:** 50K-500K users

---

## Monitoring & Alerting

### Essential Metrics Dashboard

```python
# app/api/metrics.py
from fastapi import APIRouter
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/api/metrics/health")
async def health_check():
    """System health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": await check_database_health(),
        "llm_api": await check_llm_health(),
    }

@router.get("/api/metrics/stats")
async def get_stats():
    """Real-time statistics"""
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    return {
        "active_sessions": await get_active_session_count(),
        "completed_today": await get_completed_count(since=today),
        "completion_rate_7d": await get_completion_rate(days=7),
        "avg_duration_minutes": await get_avg_duration(days=7),
        "error_rate_1h": await get_error_rate(hours=1),
    }
```

### Alert Thresholds

```yaml
# alerts.yaml
alerts:
  - name: high_error_rate
    condition: error_rate_1h > 0.02  # 2%
    severity: critical
    action: page_on_call

  - name: slow_response_time
    condition: p95_response_time > 3000  # 3s
    severity: warning
    action: slack_notification

  - name: low_completion_rate
    condition: completion_rate_7d < 0.80  # 80%
    severity: warning
    action: email_product_team

  - name: database_connection_pool_exhausted
    condition: db_pool_usage > 0.90  # 90%
    severity: critical
    action: page_on_call

  - name: llm_rate_limit_errors
    condition: llm_rate_limit_errors_5m > 10
    severity: warning
    action: enable_queue_mode
```

---

## Failure Scenarios

### 1. Database Failure

**Symptoms:** Connection timeouts, query errors

**Mitigation:**
```python
# app/database.py
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
async def get_session_with_retry(session_id: str):
    """Get session with automatic retry"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SessionData).where(SessionData.session_id == session_id)
        )
        return result.scalar_one_or_none()
```

**Recovery:**
- Automatic retry with exponential backoff
- Circuit breaker pattern after 5 consecutive failures
- Fallback to read replica if available

### 2. LLM API Failure

**Symptoms:** Timeout errors, rate limits, API downtime

**Mitigation:**
```python
# Already implemented in services.py
async def call_llm_with_fallback(conversation_history):
    providers = ["openai", "gemini", "deepseek"]

    for provider in providers:
        try:
            return await call_llm(conversation_history, provider=provider)
        except Exception as e:
            logger.warning(f"{provider} failed: {e}")
            continue

    # All providers failed - return graceful error
    return {
        "response": "We're experiencing technical difficulties. Please try again in a moment.",
        "extracted": {},
        "is_complete": False,
        "error": True
    }
```

### 3. High Load Spike

**Symptoms:** Slow response times, rate limit errors

**Mitigation:**
- Enable queue mode automatically
- Scale horizontally (add FastAPI instances)
- Increase LLM provider weights for cheaper alternatives
- Show "high traffic" message to users

### 4. Disk Space Full

**Prevention:**
```python
# monitoring/disk_check.py
import shutil

def check_disk_space():
    total, used, free = shutil.disk_usage("/")
    free_percent = (free / total) * 100

    if free_percent < 20:
        logger.critical(f"Disk space critically low: {free_percent:.1f}% free")
        # Trigger alert
    elif free_percent < 30:
        logger.warning(f"Disk space low: {free_percent:.1f}% free")
```

---

## Infrastructure Recommendations

### Phase 1: MVP (0-10K users)

```
Infrastructure:
- DigitalOcean Droplet: $12/mo (2GB RAM, 50GB SSD)
- PostgreSQL: Included on same droplet
- Backup: DigitalOcean automated backups (+20% cost)

Total: ~$15/month + LLM costs

Capacity:
- 10K users total
- ~50 concurrent sessions
- ~100MB storage
```

### Phase 2: Growth (10K-50K users)

```
Infrastructure:
- DigitalOcean Droplet: $24/mo (4GB RAM, 80GB SSD)
- Managed PostgreSQL: $15/mo (1GB RAM, separate instance)
- Redis: $5/mo (caching + queues)
- Backups: $8/mo

Total: ~$52/month + LLM costs

Capacity:
- 50K users total
- ~200 concurrent sessions
- ~1GB storage
```

### Phase 3: Scale (50K-500K users)

```
Infrastructure:
- App Servers (2x): $48/mo (2x $24 droplets behind load balancer)
- Managed PostgreSQL: $40/mo (4GB RAM, read replica)
- Redis: $15/mo (higher tier)
- Load Balancer: $12/mo
- Monitoring: $20/mo (DataDog/New Relic)
- Backups: $20/mo

Total: ~$155/month + LLM costs

Capacity:
- 500K users total
- ~1,000 concurrent sessions
- ~5GB storage
```

---

## Key Takeaways

1. **10K users is manageable** with current single-server setup
2. **Storage is cheap** - store everything for analytics
3. **LLM rate limits** are your main scaling bottleneck
4. **Multi-provider failover** is essential for reliability
5. **Connection pooling** prevents database overload
6. **Monitoring abandonment rate** is the most important metric
7. **One-time use pattern** means no sustained high load
8. **Cost per user** is $0.015-0.06 (very affordable)

---

## Next Steps

- [ ] Implement database connection pooling
- [ ] Add structured logging for all events
- [ ] Create metrics endpoint (`/api/metrics`)
- [ ] Setup basic monitoring dashboard
- [ ] Implement multi-provider LLM fallback
- [ ] Add database indexes
- [ ] Configure automated backups
- [ ] Load test with 100 concurrent sessions

---

*Last Updated: 2025-12-11*
*Document Owner: Engineering Team*
