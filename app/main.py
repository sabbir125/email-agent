import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.database.db import init_db, get_db
from app.database.models import Email
from app.api.emails import router as emails_router
from app.services.scheduler import process_emails
from app.services.email_reader import close_imap_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# APScheduler instance
scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown logic."""
    logger.info("Initializing database...")
    init_db()

    logger.info("Starting scheduler...")
    scheduler.add_job(
        process_emails,
        "interval",
        minutes=settings.SCHEDULER_INTERVAL_MINUTES,
        id="email_processor",
        replace_existing=True,
    )
    scheduler.start()

    logger.info("Running initial email processing...")
    process_emails()

    yield

    logger.info("Shutting down scheduler...")
    scheduler.shutdown(wait=False)
    close_imap_connection()
    logger.info("Application shutdown complete.")


app = FastAPI(
    title="AI Email Reading Agent",
    description="Reads emails, classifies them with OpenAI, and exposes dashboard APIs.",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="app/templates")

# Include API routes
app.include_router(emails_router)


@app.get("/")
def dashboard(request: Request):
    """Render the dashboard showing important email notifications."""
    db = next(get_db())
    try:
        emails = (
            db.query(Email)
            .filter(Email.important == True)  # noqa: E712
            .order_by(Email.received_at.desc())
            .all()
        )
        total = db.query(Email).count()
        important = db.query(Email).filter(Email.important == True).count()  # noqa: E712
        ignored = total - important
        stats = {"total": total, "important": important, "ignored": ignored}
    finally:
        db.close()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "emails": emails,
            "stats": stats,
            "interval": settings.SCHEDULER_INTERVAL_MINUTES,
        },
    )


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
