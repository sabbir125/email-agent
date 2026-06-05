import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database.models import Email
from app.schemas.email import EmailResponse, StatsResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/emails", response_model=List[EmailResponse])
def get_all_emails(db: Session = Depends(get_db)) -> List[Email]:
    """Return all processed emails ordered by received date descending."""
    try:
        emails = db.query(Email).order_by(Email.received_at.desc()).all()
        return emails
    except Exception as e:
        logger.error(f"Error fetching emails: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch emails.")


@router.get("/emails/important", response_model=List[EmailResponse])
def get_important_emails(db: Session = Depends(get_db)) -> List[Email]:
    """Return only emails classified as important."""
    try:
        emails = (
            db.query(Email)
            .filter(Email.important == True)  
            .order_by(Email.received_at.desc())
            .all()
        )
        return emails
    except Exception as e:
        logger.error(f"Error fetching important emails: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch important emails.")


@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)) -> StatsResponse:
    """Return email processing statistics."""
    try:
        total = db.query(Email).count()
        important = db.query(Email).filter(Email.important == True).count()  # noqa: E712
        ignored = total - important
        return StatsResponse(total=total, important=important, ignored=ignored)
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch stats.")
