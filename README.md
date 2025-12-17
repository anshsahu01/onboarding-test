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

## Documentation

See the `docs/` folder for more detailed information:
- `SETUP_DATABASE.md` - Detailed database setup
- `DATABASE_SCHEMA.md` - Database structure
- `SCALING_GUIDE.md` - Scaling considerations

## Support

If you encounter any issues, check the logs in the application output or enable `DEBUG=True` in `.env` for more detailed error messages.
