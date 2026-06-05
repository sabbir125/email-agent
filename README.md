# AI Email Agent

An AI-powered email monitoring agent that reads emails, classifies them using OpenAI, and displays a live dashboard. Supports both a mock JSON source (for testing) and Gmail via IMAP.

## Features

- Reads emails from Gmail (IMAP) or a local mock JSON file
- Classifies emails with OpenAI into categories: `PAYMENT_ISSUE`, `SERVER_DOWN`, `CUSTOMER_COMPLAINT`, `ACCOUNT_ACCESS`, `GENERAL_SUPPORT`, `NEWSLETTER`, `SPAM`
- Assigns a priority (`HIGH`, `MEDIUM`, `LOW`) and importance flag
- Persists results to SQLite
- Live dashboard at `/` with real-time polling and toast notifications
- REST API endpoints for emails and stats
- Background scheduler that polls for new emails on a configurable interval

## Tech Stack

- **FastAPI** — web framework & REST API
- **APScheduler** — background email polling
- **SQLAlchemy** — ORM with SQLite
- **OpenAI API** — email classification (`gpt-4.1-mini` by default)
- **Jinja2 + Tailwind CSS** — dashboard UI
- **Docker** — containerized deployment

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
├── .env                # Environment variables (not committed)
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Setup

### 1. Environment variables

Copy the example below into a `.env` file in the project root:

```env
# Required
OPENAI_API_KEY=sk-...

# Database (default: local SQLite)
DATABASE_URL=sqlite:///./data/emails.db

# Scheduler
SCHEDULER_INTERVAL_MINUTES=2

# OpenAI
OPENAI_MODEL=gpt-4.1-mini
OPENAI_TIMEOUT=30

# Email source: "mock" or "gmail"
EMAIL_SOURCE=mock

# Mock data path (used when EMAIL_SOURCE=mock)
MOCK_DATA_PATH=mock_data/emails.json

# Gmail IMAP (required when EMAIL_SOURCE=gmail)
GMAIL_USER=you@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
GMAIL_MAX_EMAILS=20
GMAIL_FOLDER=INBOX
```

> For Gmail, you must enable IMAP and generate an [App Password](https://support.google.com/accounts/answer/185833).

### 2. Run with Docker (recommended)

```bash
docker compose up --build
```

The app will be available at [http://localhost:8000](http://localhost:8000).

The SQLite database is persisted in a named Docker volume (`email_data`).

### 3. Run locally

```bash
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

| Method | Endpoint           | Description                        |
|--------|--------------------|------------------------------------|
| GET    | `/`                | Dashboard (HTML)                   |
| GET    | `/emails`          | All processed emails (JSON)        |
| GET    | `/emails/important`| Important emails only (JSON)       |
| GET    | `/stats`           | Email processing stats (JSON)      |
| GET    | `/health`          | Health check                       |

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

| Variable                    | Default                    | Description                              |
|-----------------------------|----------------------------|------------------------------------------|
| `OPENAI_API_KEY`            | *(required)*               | Your OpenAI API key                      |
| `DATABASE_URL`              | `sqlite:///./data/emails.db` | SQLAlchemy database URL                |
| `SCHEDULER_INTERVAL_MINUTES`| `2`                        | How often to poll for new emails         |
| `OPENAI_MODEL`              | `gpt-4.1-mini`             | OpenAI model for classification          |
| `OPENAI_TIMEOUT`            | `30`                       | OpenAI request timeout in seconds        |
| `EMAIL_SOURCE`              | `mock`                     | `mock` or `gmail`                        |
| `MOCK_DATA_PATH`            | `mock_data/emails.json`    | Path to mock email data                  |
| `GMAIL_USER`                | —                          | Gmail address (for `gmail` source)       |
| `GMAIL_APP_PASSWORD`        | —                          | Gmail App Password (for `gmail` source)  |
| `GMAIL_MAX_EMAILS`          | `20`                       | Max emails to fetch per poll             |
| `GMAIL_FOLDER`              | `INBOX`                    | Comma-separated IMAP folders to watch   |
