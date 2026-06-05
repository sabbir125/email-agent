# AI Email Agent

An AI-powered email monitoring agent that reads emails, classifies them using OpenAI, and displays a live dashboard. Supports both a mock JSON source (for testing) and Gmail via IMAP.

## Features

- Reads emails from Gmail (IMAP) or a local mock JSON file
- Classifies emails with OpenAI into categories: `PAYMENT_ISSUE`, `SERVER_DOWN`, `CUSTOMER_COMPLAINT`, `ACCOUNT_ACCESS`, `GENERAL_SUPPORT`, `NEWSLETTER`, `SPAM`
- Assigns a priority (`HIGH`, `MEDIUM`, `LOW`) and importance flag
- Persists results to **PostgreSQL** (local Docker or Neon cloud)
- Live dashboard at `/` with real-time polling and toast notifications
- REST API endpoints for emails and stats
- Background scheduler that polls for new emails on a configurable interval
- Serverless-aware: skips the background scheduler when `VERCEL=1` is set

## Tech Stack

- **FastAPI**: web framework & REST API
- **APScheduler**: background email polling
- **SQLAlchemy + psycopg2**: ORM with PostgreSQL
- **OpenAI API**: email classification (`gpt-4.1-mini` by default)
- **Jinja2 + Tailwind CSS**: dashboard UI
- **Docker + PostgreSQL 16**: containerized deployment

## Project Structure

```
email-agent/
├── app/
│   ├── api/            # FastAPI route handlers
│   ├── database/       # SQLAlchemy models and session management
│   ├── schemas/        # Pydantic schemas
│   ├── services/       # Email reader, classifier, scheduler
│   ├── static/         # Static assets
│   ├── templates/      # Jinja2 HTML templates
│   ├── config.py       # Settings loaded from environment
│   └── main.py         # App entry point and lifespan
├── mock_data/
│   └── emails.json     # Sample emails for mock mode
├── .env.example        # Environment variable template
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Setup

### 1. Environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```env
OPENAI_API_KEY=sk-...

# ─── Database ─────────────────────────────────────────────────────────────────
# Local Docker:  postgresql+psycopg2://postgres:postgres@localhost:5432/emailagent
# Neon (cloud):  postgresql+psycopg2://user:pass@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/emailagent

SCHEDULER_INTERVAL_MINUTES=2
OPENAI_MODEL=gpt-4.1-mini
OPENAI_TIMEOUT=30

# ─── Email Source ─────────────────────────────────────────────────────────────
# "mock" reads from mock_data/emails.json
# "gmail" connects via IMAP
EMAIL_SOURCE=mock

MOCK_DATA_PATH=mock_data/emails.json

# ─── Gmail IMAP (required when EMAIL_SOURCE=gmail) ───────────────────────────
GMAIL_USER=you@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
GMAIL_MAX_EMAILS=20
GMAIL_FOLDER=INBOX
```

> For Gmail, enable IMAP and generate an [App Password](https://support.google.com/accounts/answer/185833).

### 2. Run with Docker (recommended)

```bash
docker compose up --build
```

This starts two containers:
- `email-agent-db` — PostgreSQL 16, data persisted in the `email_db_data` volume
- `ai-email-agent` — the FastAPI app, available at [http://localhost:8000](http://localhost:8000)

The app container waits for the database health check to pass before starting.

### 3. Run locally

You need a running PostgreSQL instance. The quickest way is to start just the database container:

```bash
docker compose up db -d
```

Then run the app:

```bash
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Make sure `DATABASE_URL` in your `.env` points to your local Postgres instance.

### 4. Using Neon (serverless Postgres)

Create a free database at [neon.tech](https://neon.tech) and set `DATABASE_URL` to your Neon connection string:

```env
DATABASE_URL=postgresql+psycopg2://user:pass@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
```

Tables are created automatically on first startup via `init_db()`.

## API Endpoints

| Method | Endpoint             | Description                        |
|--------|----------------------|------------------------------------|
| GET    | `/`                  | Dashboard (HTML)                   |
| GET    | `/emails`            | All processed emails (JSON)        |
| GET    | `/emails/important`  | Important emails only (JSON)       |
| GET    | `/stats`             | Email processing stats (JSON)      |
| GET    | `/health`            | Health check                       |

## Email Categories

| Category             | Description                          |
|----------------------|--------------------------------------|
| `PAYMENT_ISSUE`      | Payment failures or billing problems |
| `SERVER_DOWN`        | Infrastructure or outage alerts      |
| `CUSTOMER_COMPLAINT` | Customer dissatisfaction             |
| `ACCOUNT_ACCESS`     | Login issues or security alerts      |
| `GENERAL_SUPPORT`    | General support requests             |
| `NEWSLETTER`         | Marketing and newsletters            |
| `SPAM`               | Spam or irrelevant emails            |

## Configuration Reference

| Variable                    | Default                                              | Description                                      |
|-----------------------------|------------------------------------------------------|--------------------------------------------------|
| `OPENAI_API_KEY`            | *(required)*                                         | Your OpenAI API key                              |
| `DATABASE_URL`              | *(required)*                                         | PostgreSQL connection string (psycopg2 format)   |
| `SCHEDULER_INTERVAL_MINUTES`| `2`                                                  | How often to poll for new emails                 |
| `OPENAI_MODEL`              | `gpt-4.1-mini`                                       | OpenAI model for classification                  |
| `OPENAI_TIMEOUT`            | `30`                                                 | OpenAI request timeout in seconds                |
| `EMAIL_SOURCE`              | `mock`                                               | `mock` or `gmail`                                |
| `MOCK_DATA_PATH`            | `mock_data/emails.json`                              | Path to mock email data                          |
| `GMAIL_USER`                | —                                                    | Gmail address (for `gmail` source)               |
| `GMAIL_APP_PASSWORD`        | —                                                    | Gmail App Password (for `gmail` source)          |
| `GMAIL_MAX_EMAILS`          | `20`                                                 | Max emails to fetch per poll                     |
| `GMAIL_FOLDER`              | `INBOX`                                              | IMAP folder(s) to watch                          |
| `VERCEL`                    | —                                                    | Set to `1` to disable background scheduler       |
