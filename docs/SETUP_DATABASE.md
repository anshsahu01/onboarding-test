# Database Setup Guide

## Quick Start

Follow these steps to set up the database (works for both local PostgreSQL and DigitalOcean).

---

## Step 1: Install PostgreSQL Locally

### Option A: Official Installer (Windows)

1. Download PostgreSQL: https://www.postgresql.org/download/windows/
2. Install with default settings:
   - Port: `5432`
   - Username: `postgres`
   - Password: Choose something simple like `postgres123`
3. pgAdmin 4 will be installed automatically (GUI tool)

### Option B: Docker

```bash
docker run --name postgres-local \
  -e POSTGRES_PASSWORD=postgres123 \
  -e POSTGRES_DB=onboarding_db \
  -p 5432:5432 \
  -d postgres:15
```

---

## Step 2: Create Database

### Using pgAdmin (GUI):
1. Open pgAdmin 4
2. Right-click "Databases" → "Create" → "Database"
3. Name: `onboarding_db`
4. Save

### Using Command Line:
```bash
psql -U postgres
CREATE DATABASE onboarding_db;
\q
```

---

## Step 3: Update .env File

Edit `e:\Pyton Tutorial\.env`:

### For Local PostgreSQL:
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres123@localhost:5432/onboarding_db
```

### For DigitalOcean (later):
```env
DATABASE_URL=postgresql+asyncpg://username:password@YOUR_DROPLET_IP:5432/onboarding_db
```

**That's it! Same code works for both - just change the URL!**

---

## Step 4: Install Python Dependencies

```bash
cd "e:\Pyton Tutorial"
pip install -r requirements.txt
```

This installs:
- sqlalchemy (ORM)
- asyncpg (PostgreSQL driver)
- alembic (migrations)
- pydantic-settings (config management)

---

## Step 5: Test Database Connection

```bash
python -m app.db.connection
```

Expected output:
```
============================================================
🔍 Testing Database Connection
============================================================

Database URL: postgresql+asyncpg://****@localhost:5432/onboarding_db
Pool Size: 10
Environment: development

🔌 Attempting to connect...
✅ Database connection successful!
============================================================
```

---

## Step 6: Initialize Database Tables

```bash
python scripts/init_db.py
```

This will:
1. Validate configuration
2. Test connection
3. Create all 4 tables:
   - `users`
   - `onboarding_sessions`
   - `user_profiles`
   - `conversation_messages`

---

## Step 7: Verify Tables Created

### Using pgAdmin:
1. Open pgAdmin 4
2. Navigate to: Servers → PostgreSQL → Databases → onboarding_db → Schemas → public → Tables
3. You should see 4 tables

### Using psql:
```bash
psql -U postgres -d onboarding_db
\dt
```

---

## Switching to DigitalOcean

### When you're ready to move to production:

1. **On Your DigitalOcean Droplet**, create the database:
   ```bash
   sudo -u postgres psql
   CREATE DATABASE onboarding_db;
   CREATE USER your_user WITH PASSWORD 'secure_password';
   GRANT ALL PRIVILEGES ON DATABASE onboarding_db TO your_user;
   \q
   ```

2. **Allow remote connections** (edit postgresql.conf and pg_hba.conf)

3. **Update .env on your local machine**:
   ```env
   DATABASE_URL=postgresql+asyncpg://your_user:secure_password@YOUR_DROPLET_IP:5432/onboarding_db
   ```

4. **Run init script again**:
   ```bash
   python scripts/init_db.py
   ```

**That's it! No code changes needed!**

---

## Troubleshooting

### Error: "FATAL: database 'onboarding_db' does not exist"
**Solution:** Create the database first (see Step 2)

### Error: "FATAL: password authentication failed"
**Solution:** Check your password in .env matches PostgreSQL password

### Error: "could not connect to server"
**Solution:**
- Check if PostgreSQL is running: `pg_ctl status`
- Check port 5432 is not blocked by firewall

### Error: "pip install failed for psycopg2-binary"
**Solution (Windows):** Install Visual C++ Build Tools or use pre-built wheel:
```bash
pip install psycopg2-binary --only-binary :all:
```

---

## Database Structure

```
users (1) ──────── (N) onboarding_sessions
  │                          │
  │(1)                      (1)
  └──── (1) user_profiles (1)┘
                │
                └──── (N) conversation_messages
```

### Table Purposes:

| Table | Purpose | Records (10K users) |
|-------|---------|---------------------|
| **users** | Core user identity | 10,000 |
| **onboarding_sessions** | Track attempts | 10,000-15,000 |
| **user_profiles** | Your 6 collected fields | 10,000 |
| **conversation_messages** | Full chat history | 100,000 |

---

## Configuration Files

### app/core/config.py
- Loads environment variables
- Type-safe settings
- Validates configuration

### app/db/connection.py
- Database engine with connection pooling
- Session management
- Health checks

### app/db/models.py
- SQLAlchemy models (4 tables)
- Relationships and constraints
- Indexes for performance

---

## Next Steps

1. ✅ Database is ready
2. ⬜ Integrate database with your existing code
3. ⬜ Refactor `app/database.py` to use PostgreSQL
4. ⬜ Test onboarding API with real database
5. ⬜ Setup Alembic for migrations (for future schema changes)

---

## Environment Variables Summary

```env
# Required
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db_name

# Optional (with defaults)
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600
DB_ECHO=False

# LLM (you already have these)
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
```

---

*Last Updated: 2025-12-11*
