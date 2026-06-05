# AI Email Agent

An AI-powered email monitoring agent that reads emails, classifies them using OpenAI, and displays a live dashboard. Supports both a mock JSON source (for testing) and Gmail via IMAP.

---

## Features

- Reads emails from Gmail (IMAP) or a local mock JSON file
- Classifies emails with OpenAI into categories: `PAYMENT_ISSUE`, `SERVER_DOWN`, `CUSTOMER_COMPLAINT`, `ACCOUNT_ACCESS`, `GENERAL_SUPPORT`, `NEWSLETTER`, `SPAM`
- Assigns a priority (`HIGH`, `MEDIUM`, `LOW`) and importance flag
- Persists results to **PostgreSQL** (local Docker or Neon cloud)
- Live dashboard at `/` with real-time polling, filter tabs, and toast notifications
- REST API endpoints for emails and stats
- Background scheduler that polls for new emails on a configurable interval
- Serverless-aware: skips the background scheduler when `VERCEL=1` is set

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web framework & API | FastAPI |
| Background scheduling | APScheduler |
| ORM & database driver | SQLAlchemy + psycopg2 |
| AI classification | OpenAI API (`gpt-4.1-mini` by default) |
| Dashboard UI | Jinja2 + Tailwind CSS |
| Database | PostgreSQL 16 |
| Containerisation | Docker + Docker Compose |

---

## Project Structure

```
email-agent/
├── app/
│   ├── api/
│   │   └── emails.py        # GET /emails, /emails/important, /stats
│   ├── database/
│   │   ├── db.py            # SQLAlchemy engine, session factory, init_db()
│   │   └── models.py        # Email ORM model
│   ├── schemas/
│   │   └── email.py         # Pydantic schemas: RawEmail, ClassificationResult, EmailResponse
│   ├── services/
│   │   ├── classifier.py    # OpenAI classification logic
│   │   ├── email_reader.py  # Mock loader + Gmail IMAP reader
│   │   └── scheduler.py     # Dedup, classify, and persist loop
│   ├── static/              # Static assets (currently empty placeholder)
│   ├── templates/
│   │   └── dashboard.html   # Jinja2 + Tailwind dashboard
│   ├── config.py            # Pydantic settings loaded from environment
│   └── main.py              # FastAPI app, lifespan, scheduler bootstrap
├── mock_data/
│   └── emails.json          # Sample emails for mock mode
├── .env.example             # Environment variable template
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

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

---

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

Then install dependencies and start the app:

```bash
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Make sure `DATABASE_URL` in your `.env` points to your local Postgres instance. Tables are created automatically on first startup via `init_db()`.

### 4. Using Neon (serverless Postgres)

Create a free database at [neon.tech](https://neon.tech) and set `DATABASE_URL` to your Neon connection string:

```env
DATABASE_URL=postgresql+psycopg2://user:pass@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
```

---

## AI Classification Logic

Email classification is handled in `app/services/classifier.py` using the OpenAI Chat Completions API.

### How it works

1. **Prompt construction** - The classifier builds a user prompt containing the sender address, subject, and body. A fixed system prompt instructs the model to respond with a strict JSON object and nothing else.

2. **Model call** - The request is sent to the configured model (default: `gpt-4.1-mini`) with `temperature=0.1` to keep outputs deterministic, and `max_tokens=256` since the response is small and structured.

3. **Response parsing** - The raw response is stripped of any accidental markdown fencing (` ``` `) before being parsed as JSON and validated against the `ClassificationResult` Pydantic schema.

4. **Failure handling** - Any `JSONDecodeError`, `OpenAIError`, or unexpected exception returns `None`. The scheduler logs the failure and skips persisting that email, so a single bad response never blocks the rest of the batch.

### Output schema

```json
{
  "important": true,
  "priority": "HIGH",
  "category": "SERVER_DOWN",
  "confidence": 94,
  "reason": "Email reports a production outage affecting all users."
}
```

### Classification categories

| Category | Description |
|---|---|
| `PAYMENT_ISSUE` | Payment failures or billing problems |
| `SERVER_DOWN` | Infrastructure or outage alerts |
| `CUSTOMER_COMPLAINT` | Customer dissatisfaction |
| `ACCOUNT_ACCESS` | Login issues or security alerts |
| `GENERAL_SUPPORT` | General support requests |
| `NEWSLETTER` | Marketing and newsletters |
| `SPAM` | Spam or irrelevant emails |

### Priority and importance rules

The model determines both `priority` and `important` independently based on content. In practice:
- `SERVER_DOWN` and `PAYMENT_ISSUE` typically resolve to `HIGH` priority and `important: true`
- `NEWSLETTER` and `SPAM` typically resolve to `LOW` priority and `important: false`
- The `confidence` field (0–100) reflects the model's self-reported certainty

---

## Dashboard

The dashboard is served at `http://localhost:8000/` and rendered server-side via Jinja2 on first load. After that, the page updates itself every **30 seconds** by polling the REST API — no page reload required.

### Stats bar

Three cards at the top show live counts: **Total Processed**, **Important**, and **Ignored**. These update on every poll cycle.

### Filter tabs

- **Important** (default) — shows only emails where `important = true`, ordered by received date descending
- **All Emails** — shows the full inbox regardless of importance flag

### Email cards

Each card displays:
- Priority badge (colour-coded: red = HIGH, amber = MEDIUM, green = LOW)
- Category tag
- Subject and sender
- AI-generated reason for the classification
- Received timestamp and confidence percentage
- A pulsing **NEW** badge for emails that arrived after the page was loaded

### Toast notifications

When the poller detects an email that wasn't present on the previous fetch, a slide-in toast appears in the bottom-right corner for 5 seconds. This fires only for important emails, regardless of which filter tab is active.

### Bell badge

The notification bell in the header tracks unread important email count. The count persists across page reloads via `localStorage` and is cleared by clicking the bell.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Dashboard (HTML) |
| `GET` | `/emails` | All processed emails (JSON) |
| `GET` | `/emails/important` | Important emails only (JSON) |
| `GET` | `/stats` | Email processing stats (JSON) |
| `GET` | `/health` | Health check |

Interactive docs are available at `/docs` (Swagger UI) and `/redoc`.

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | Your OpenAI API key |
| `DATABASE_URL` | *(required)* | PostgreSQL connection string (psycopg2 format) |
| `SCHEDULER_INTERVAL_MINUTES` | `2` | How often to poll for new emails |
| `OPENAI_MODEL` | `gpt-4.1-mini` | OpenAI model used for classification |
| `OPENAI_TIMEOUT` | `30` | OpenAI request timeout in seconds |
| `EMAIL_SOURCE` | `mock` | `mock` or `gmail` |
| `MOCK_DATA_PATH` | `mock_data/emails.json` | Path to mock email data file |
| `GMAIL_USER` | — | Gmail address (required for `gmail` source) |
| `GMAIL_APP_PASSWORD` | — | Gmail App Password (required for `gmail` source) |
| `GMAIL_MAX_EMAILS` | `20` | Max emails to fetch per folder per poll |
| `GMAIL_FOLDER` | `INBOX` | Comma-separated IMAP folder(s) to watch |
| `VERCEL` | — | Set to `1` to disable the background scheduler |

---

## Limitations

- Classification is based on subject and body text only. Emails with vague or minimal content may receive low confidence scores or be miscategorised.
- `gpt-4.1-mini` handles the majority of cases well, but ambiguous or non-English emails may not classify correctly. Swapping to a larger model via `OPENAI_MODEL` will improve accuracy.
- Deduplication relies on the `Message-ID` header. Emails redelivered by a mail server with a different `Message-ID` (e.g. via certain forwarding rules) could be stored twice.
- In mock mode, the same `emails.json` file is read on every poll cycle. Already-processed emails are skipped by the duplicate check, so this has no visible effect unless you add new entries to the file.
