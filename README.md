# Onboarding Feature

This is a backend service for testing the onboarding feature. The founder can quickly set it up locally by following these steps.

## Prerequisites

- Python 3.10+
- PostgreSQL installed and running locally
- Git

## Quick Setup (5 minutes)

### Step 1: Clone/Extract the Project
```bash
# If using git
git clone <repository-url>
cd Onboarding

# Or extract the zip file and navigate to the directory
cd Onboarding
```

### Step 2: Create Virtual Environment
```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 4: Set Up Environment Variables
```powershell
# Copy the example env file
Copy-Item .env.example -Destination .env

# Edit .env file with your local PostgreSQL credentials
# Open .env in your editor and update:
# DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/onboarding_db
```

**Required environment variables to update:**
- `DATABASE_URL` - Your local PostgreSQL connection string
- `LLM_PROVIDER` - Set to your preferred LLM (openai, gemini, or deepseek)
- `OPENAI_API_KEY` (or relevant API key for your chosen provider)

### Step 5: Initialize Database
```powershell
# Run database migrations
alembic upgrade head

# Or if first time setup, create tables
python create_tables.py
```

### Step 6: Start the Server
```powershell
# Run the main application
python main.py
```

The server will start at `http://localhost:8000` (or the configured port).

## Running Tests

```powershell
# Run test startup
python test_startup.py

# Run test request
python test_request.py

# Or run the test shell script
bash test_onboarding.sh
```

## Database Access

Once set up, you can verify the database:
```powershell
# Check tables (uses included script)
python scripts/check_tables.py
```

## Troubleshooting

### PostgreSQL Connection Issues
- Ensure PostgreSQL is running: `pg_isready` (in your PostgreSQL bin folder)
- Verify credentials in `.env` file match your PostgreSQL setup
- Check default PostgreSQL user is `postgres` with port `5432`

### Migration Issues
```powershell
# If migrations fail, check status
alembic current

# View migration history
alembic history

# Rollback if needed
alembic downgrade -1
```

### Dependency Issues
```powershell
# Reinstall dependencies
pip install --upgrade -r requirements.txt
```

## Project Structure

```
├── app/                    # Main application code
│   ├── models.py          # Pydantic models
│   ├── services.py        # Business logic
│   ├── database.py        # Database connection
│   └── db_operations.py   # Database queries
├── alembic/              # Database migrations
├── main.py               # Application entry point
├── create_tables.py      # Initial setup
└── .env.example          # Environment template
```



## API Documentation

The API is built with FastAPI and runs at `http://localhost:8000` by default.

### 1. Health Check
Check if the API is running.

**Endpoint:** `GET /`

**Response:**
```json
{
  "status": "ok",
  "service": "Onboarding API",
  "version": "1.0.0"
}
```

**Test:** 
- Browser: http://localhost:8000/
- Or use the **Interactive API Docs** at http://localhost:8000/docs

---

### 2. Start Onboarding Session
Initialize a new onboarding session for a user. Returns the first question.

**Endpoint:** `POST /api/onboarding/start`

**Request Body:**
```json
{
  "user_id": "user_123"
}
```

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "success": true,
  "response": "Welcome! Let's start with your name. What should we call you?",
  "is_complete": false,
  "profile": null
}
```

**cURL:**
```bash
curl -X POST http://localhost:8000/api/onboarding/start \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_123"}'
```

---

### 3. Submit Answer & Get Next Question
Submit an answer to a question and receive the next question or completion status.

**Endpoint:** `POST /api/onboarding/answer`

**Request Body:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "answer": "John Doe"
}
```

**Response (In Progress):**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "success": true,
  "response": "Nice to meet you, John! What role are you looking for at a startup?",
  "is_complete": false,
  "profile": null
}
```

**Response (Completed):**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "success": true,
  "response": "Thank you for completing the onboarding!",
  "is_complete": true,
  "profile": {
    "name": "John Doe",
    "role": "Product Manager",
    "experience_level": "3-5 years",
    "location": "San Francisco, CA",
    "startup_stage": "Series A",
    "extra_preferences": "Open to relocation"
  },
  "completion_message": "🎉 Welcome aboard! 🎉"
}
```

**cURL:**
```bash
curl -X POST http://localhost:8000/api/onboarding/answer \
  -H "Content-Type: application/json" \
  -d '{"session_id": "550e8400-e29b-41d4-a716-446655440000", "answer": "John Doe"}'
```

---

### 4. Get Session Details
Retrieve the current state of an onboarding session including conversation history and profile data.

**Endpoint:** `GET /api/onboarding/session/{session_id}`

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user_123",
  "status": "completed",
  "profile": {
    "name": "John Doe",
    "role": "Product Manager",
    "experience_level": "3-5 years",
    "location": "San Francisco, CA",
    "startup_stage": "Series A",
    "extra_preferences": "Open to relocation"
  },
  "conversation_history": [
    {
      "role": "assistant",
      "content": "Welcome! Let's start with your name...",
      "timestamp": "2025-12-17T10:00:00"
    },
    {
      "role": "user",
      "content": "John Doe",
      "timestamp": "2025-12-17T10:00:05"
    }
  ],
  "created_at": "2025-12-17T10:00:00"
}
```

**cURL:**
```bash
curl http://localhost:8000/api/onboarding/session/550e8400-e29b-41d4-a716-446655440000
```

---

### Testing the APIs

#### Option 1: Interactive Swagger UI (Recommended)
Once the server is running, visit: **http://localhost:8000/docs**

This provides an interactive interface where you can:
1. Click on each endpoint
2. Fill in parameters
3. Click "Try it out"
4. See responses in real-time

#### Option 2: Postman
1. Import the collection or create requests manually:
   - Start a session with `/api/onboarding/start`
   - Copy the `session_id` from response
   - Use that `session_id` to submit answers with `/api/onboarding/answer`
   - Retrieve session details with `/api/onboarding/session/{session_id}`

#### Option 3: Command Line (cURL)
See the cURL examples above for each endpoint.

#### Option 4: Python Test Scripts
Run the included test scripts:
```powershell
# Test the flow
python test_request.py

# Or run the bash test
bash test_onboarding.sh
```

---

### Complete Flow Example

```bash
# Step 1: Start session
RESPONSE=$(curl -s -X POST http://localhost:8000/api/onboarding/start \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_123"}')

SESSION_ID=$(echo $RESPONSE | jq -r '.session_id')
echo "Session ID: $SESSION_ID"

# Step 2: Answer first question
curl -s -X POST http://localhost:8000/api/onboarding/answer \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION_ID\", \"answer\": \"John Doe\"}"

# Step 3: Continue answering questions...
# Repeat step 2 with different answers until is_complete is true

# Step 4: Get final session data
curl http://localhost:8000/api/onboarding/session/$SESSION_ID
```

---

## Support

If you encounter any issues, check the logs in the application output or enable `DEBUG=True` in `.env` for more detailed error messages.

## Documentation

See the `docs/` folder for more detailed information:
- `SETUP_DATABASE.md` - Detailed database setup
- `DATABASE_SCHEMA.md` - Database structure
- `SCALING_GUIDE.md` - Scaling considerations

## Support

If you encounter any issues, check the logs in the application output or enable `DEBUG=True` in `.env` for more detailed error messages.
