import email
import email.utils
import imaplib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from email.header import decode_header
from pathlib import Path
from typing import List, Optional

from app.config import get_settings
from app.schemas.email import RawEmail

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Persistent IMAP connection (module-level singleton)
# ---------------------------------------------------------------------------

_imap_conn: Optional[imaplib.IMAP4_SSL] = None


def _get_imap_connection() -> imaplib.IMAP4_SSL:
    """Return a live IMAP connection, (re)connecting only when necessary.

    Reuses the existing connection across scheduler runs. Reconnects if the
    connection has been dropped or timed out by the server.
    """
    global _imap_conn
    settings = get_settings()

    def _connect() -> imaplib.IMAP4_SSL:
        logger.info(f"Connecting to Gmail IMAP as {settings.GMAIL_USER}...")
        conn = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        conn.login(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)
        logger.info("IMAP login successful.")
        return conn

    if _imap_conn is None:
        _imap_conn = _connect()
        return _imap_conn

    # Check if the connection is still alive with a cheap NOOP
    try:
        status, _ = _imap_conn.noop()
        if status == "OK":
            return _imap_conn
        raise imaplib.IMAP4.error("NOOP returned non-OK status")
    except Exception as e:
        logger.warning(f"IMAP connection lost ({e}), reconnecting...")
        try:
            _imap_conn.logout()
        except Exception:
            pass
        _imap_conn = _connect()
        return _imap_conn


def close_imap_connection() -> None:
    """Gracefully close the persistent IMAP connection (called on app shutdown)."""
    global _imap_conn
    if _imap_conn is not None:
        try:
            _imap_conn.logout()
            logger.info("IMAP connection closed.")
        except Exception:
            pass
        _imap_conn = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode_mime_words(raw: str) -> str:
    """Decode MIME-encoded header words (e.g. =?utf-8?b?...?=) to plain text."""
    parts = decode_header(raw or "")
    decoded = []
    for chunk, charset in parts:
        if isinstance(chunk, bytes):
            decoded.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(chunk)
    return "".join(decoded)


def _extract_email_address(raw_from: str) -> str:
    """Extract the bare email address from a From header.

    Handles formats like:
      - "John Doe <john@example.com>"          → "john@example.com"
      - "=?UTF-8?b?R29vZ2xl?= <x@google.com>" → "x@google.com"
      - "john@example.com"                     → "john@example.com"

    Strategy: run parseaddr on the raw header first (it handles angle-bracket
    syntax reliably), then decode only the extracted address portion to strip
    any residual MIME encoding.
    """
    # First pass on raw header — parseaddr handles "Name <addr>" reliably
    _, addr = email.utils.parseaddr(raw_from or "")

    if addr:
        # Decode any MIME encoding left in the address itself
        return _decode_mime_words(addr).strip().lower()

    # No angle-bracket address found — decode the whole string and retry
    decoded = _decode_mime_words(raw_from or "")
    _, addr2 = email.utils.parseaddr(decoded)
    return addr2.strip().lower() if addr2 else decoded.strip().lower()


def _extract_body(msg: email.message.Message) -> str:
    """Return the plain-text body of an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                charset = part.get_content_charset() or "utf-8"
                return part.get_payload(decode=True).decode(charset, errors="replace")
        # Fallback: strip HTML tags from first text/html part
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                charset = part.get_content_charset() or "utf-8"
                html = part.get_payload(decode=True).decode(charset, errors="replace")
                return re.sub(r"<[^>]+>", " ", html).strip()
    else:
        charset = msg.get_content_charset() or "utf-8"
        return msg.get_payload(decode=True).decode(charset, errors="replace")

    return ""


# ---------------------------------------------------------------------------
# Mock loader
# ---------------------------------------------------------------------------

def load_mock_emails() -> List[RawEmail]:
    """Load and parse emails from the mock JSON data file."""
    settings = get_settings()
    file_path = Path(settings.MOCK_DATA_PATH)

    if not file_path.exists():
        logger.error(f"Mock data file not found: {file_path}")
        raise FileNotFoundError(f"Email data file not found: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in mock data file: {e}")
        raise

    emails: List[RawEmail] = []
    for item in raw_data:
        try:
            emails.append(RawEmail.model_validate(item))
        except Exception as e:
            logger.warning(f"Skipping invalid mock email entry: {e}")

    logger.info(f"Loaded {len(emails)} mock emails from {file_path}")
    return emails


# ---------------------------------------------------------------------------
# Gmail IMAP loader
# ---------------------------------------------------------------------------

def _fetch_from_folder(mail: imaplib.IMAP4_SSL, folder: str, max_emails: int) -> List[RawEmail]:
    """Fetch up to max_emails from a single IMAP folder."""
    try:
        status, _ = mail.select(folder, readonly=True)
        if status != "OK":
            logger.warning(f"Could not select folder '{folder}', skipping.")
            return []
    except Exception as e:
        logger.warning(f"Error selecting folder '{folder}': {e}")
        return []

    status, data = mail.search(None, "ALL")
    if status != "OK" or not data or not data[0]:
        return []

    all_ids = data[0].split()
    selected_ids = list(reversed(all_ids[-max_emails:]))  # newest first

    emails: List[RawEmail] = []
    for msg_id in selected_ids:
        try:
            status, msg_data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data or msg_data[0] is None:
                continue

            raw_bytes = msg_data[0][1]
            msg = email.message_from_bytes(raw_bytes)

            subject = _decode_mime_words(msg.get("Subject", "(no subject)"))
            from_address = _extract_email_address(msg.get("From", ""))

            date_str = msg.get("Date", "")
            try:
                received_at = email.utils.parsedate_to_datetime(date_str).astimezone(timezone.utc)
            except Exception:
                received_at = datetime.now(timezone.utc)

            body = _extract_body(msg)

            # Extract clean ID from Message-ID header.
            # "<TeP1aC6j70v95S9x8yz8Ww@notifications.google.com>" → "TeP1aC6j70v95S9x8yz8Ww"
            raw_msg_id = msg.get("Message-ID", "").strip()
            # Strip surrounding angle brackets
            clean_id = raw_msg_id.strip("<>")
            # Keep only the local part before the @
            clean_id = clean_id.split("@")[0] if "@" in clean_id else clean_id
            # Final fallback if header is missing or empty
            msg_uid = clean_id if clean_id else str(uuid.uuid4())

            emails.append(RawEmail(
                id=msg_uid,
                **{"from": from_address},
                subject=subject,
                body=body,
                received_at=received_at,
            ))

        except Exception as e:
            logger.warning(f"Skipping message {msg_id} in '{folder}': {e}")
            continue

    logger.info(f"Fetched {len(emails)} emails from folder '{folder}'.")
    return emails


def load_gmail_emails() -> List[RawEmail]:
    """Fetch recent emails from Gmail via a persistent IMAP connection.

    Supports multiple folders via a comma-separated GMAIL_FOLDER value,
    e.g. INBOX,[Gmail]/Starred

    Raises:
        ValueError: If GMAIL_USER or GMAIL_APP_PASSWORD are not configured.
    """
    settings = get_settings()

    if not settings.GMAIL_USER or not settings.GMAIL_APP_PASSWORD:
        raise ValueError(
            "GMAIL_USER and GMAIL_APP_PASSWORD must be set in .env when EMAIL_SOURCE=gmail"
        )

    mail = _get_imap_connection()

    # Support comma-separated folder list
    folders = [f.strip() for f in settings.GMAIL_FOLDER.split(",") if f.strip()]

    all_emails: List[RawEmail] = []
    seen_ids: set = set()

    for folder in folders:
        for raw_email in _fetch_from_folder(mail, folder, settings.GMAIL_MAX_EMAILS):
            if raw_email.id not in seen_ids:
                seen_ids.add(raw_email.id)
                all_emails.append(raw_email)

    logger.info(f"Total fetched across {len(folders)} folder(s): {len(all_emails)} emails.")
    return all_emails


# ---------------------------------------------------------------------------
# Public entry point (used by the scheduler)
# ---------------------------------------------------------------------------

def load_emails() -> List[RawEmail]:
    """Return emails from the configured source (mock or gmail).

    Reads EMAIL_SOURCE from settings:
      - "mock"  → loads from mock_data/emails.json
      - "gmail" → fetches from Gmail via persistent IMAP connection
    """
    settings = get_settings()
    source = settings.EMAIL_SOURCE.lower().strip()

    if source == "gmail":
        return load_gmail_emails()
    else:
        logger.info("Email source: mock data")
        return load_mock_emails()
