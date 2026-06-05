from sqlalchemy import Column, String, Boolean, Integer, DateTime
from datetime import datetime, timezone

from app.database.db import Base


class Email(Base):
    """SQLAlchemy model for processed emails."""

    __tablename__ = "emails"

    email_id = Column(String, primary_key=True, index=True)
    sender = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(String, nullable=False)
    important = Column(Boolean, nullable=False, default=False)
    priority = Column(String, nullable=False, default="LOW")
    category = Column(String, nullable=False, default="GENERAL_SUPPORT")
    confidence = Column(Integer, nullable=False, default=0)
    reason = Column(String, nullable=False, default="")
    received_at = Column(DateTime, nullable=False)
    processed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<Email(email_id={self.email_id}, subject={self.subject}, priority={self.priority})>"
