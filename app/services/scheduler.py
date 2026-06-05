import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.database.models import Email
from app.services.email_reader import load_emails
from app.services.classifier import classify_email

logger = logging.getLogger(__name__)


def process_emails() -> None:
    """Process unclassified emails from the mock data source.

    Reads all emails, skips duplicates already in the database,
    classifies new ones via OpenAI, and persists the results.
    """
    logger.info("Scheduler triggered: processing emails...")

    db: Session = SessionLocal()
    try:
        emails = load_emails()
    except Exception as e:
        logger.error(f"Failed to load emails: {e}")
        db.close()
        return

    new_count = 0
    error_count = 0

    for raw_email in emails:
        # Duplicate check
        existing = db.query(Email).filter(Email.email_id == raw_email.id).first()
        if existing:
            logger.debug(f"Email {raw_email.id} already processed, skipping.")
            continue

        # Classify
        result = classify_email(raw_email)
        if result is None:
            logger.warning(f"Classification failed for email {raw_email.id}, skipping.")
            error_count += 1
            continue

        # Persist
        try:
            email_record = Email(
                email_id=raw_email.id,
                sender=raw_email.from_address,
                subject=raw_email.subject,
                body=raw_email.body,
                important=result.important,
                priority=result.priority,
                category=result.category,
                confidence=result.confidence,
                reason=result.reason,
                received_at=raw_email.received_at,
                processed_at=datetime.now(timezone.utc),
            )
            db.add(email_record)
            db.commit()
            new_count += 1
            logger.info(f"Stored email {raw_email.id}: {result.category} / {result.priority}")
        except Exception as e:
            db.rollback()
            logger.error(f"Database error storing email {raw_email.id}: {e}")
            error_count += 1

    db.close()
    logger.info(
        f"Processing complete. New: {new_count}, Errors: {error_count}, "
        f"Skipped (duplicates): {len(emails) - new_count - error_count}"
    )
